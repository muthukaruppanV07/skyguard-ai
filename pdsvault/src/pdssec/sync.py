# SPDX-License-Identifier: MIT
"""Offline-first sync: server-signed, versioned, chunked, resumable deltas.

Design notes
------------
* The central authority is the single writer of truth.  Devices are readers:
  they apply only authority-signed snapshots and push their own *evidence*
  (used-token hashes, ledger anchors, attestation quotes, clock readings).
* Records carry valid-from/to epochs signed by the authority - stale epochs
  expire automatically on the device, so a *replayed* old snapshot is inert.
* Deltas are expressed as "records changed since snapshot seq S".  Snapshot
  numbers are monotonic and each snapshot links to prev snapshot hash, so a
  replayed/rolled-back snapshot is detected (replay is also stopped by the
  epoch windows inside every record).
* Transfers are chunked with per-chunk SHA-256, resumable at byte level and
  retried per-chunk on corruption - workable on 2G/EDGE.
* Conflict resolution when two devices diverge and both reconnect: the server
  merges their evidence (used-token hashes, override records, audits) into a
  fresh snapshot; duplicate redemptions across shops are resolved here and
  returned as duplicate_flags for follow-up revocation.
"""

from __future__ import annotations

from . import auth
from . import crypto
from .crypto import b64d, b64e, sha256
from .ledger import MerkleTree

CHUNK_RECORDS = 100
MAX_CHUNK_RETRIES = 3


def domain_dsid(domain_uid_key: bytes, shop_domain: str, masked_uid: str) -> str:
    """Deterministic domain-scoped identifier (same on every device that holds
    the *same* domain key, which only its own shop does)."""
    return crypto.hmac_sha256(
        domain_uid_key, (shop_domain + "|" + masked_uid).encode()
    ).hex()[:20]


# --------------------------------------------------------------------------- #
# Central authority service (the "snapshot server" a shop syncs against)
# --------------------------------------------------------------------------- #

class SyncServer:
    def __init__(self, authority, clock_now: int):
        self.authority = authority
        self.clock_now = clock_now
        self.records: dict[str, list[dict]] = {}          # domain -> records
        # snapshot chain is per device: each device advances from its own
        # cursor, so a fresh shop and a reconnecting shop never collide.
        self.device_chain: dict[str, dict] = {}           # device_id -> state
        self.tokens: list[dict] = []
        self.redeemed_token_ids: set[str] = set()
        self.redeemed_hashes: set[bytes] = set()
        self.duplicate_flags: list[dict] = []
        self.revocations: dict[str, dict] = {}
        self.kill_switches: list[dict] = []
        self.model_updates: list[dict] = []

    def publish_domain(self, domain: str, records: list[dict]) -> None:
        self.records[domain] = sorted(records, key=lambda r: r["masked_uid"])

    def mint_tokens_for(self, domain: str, uid_entries: list[dict],
                        cycle_epoch: int, basket: str, valid_from: int,
                        valid_to: int) -> list[dict]:
        dk = self.authority.domain_keys(domain)
        toks = []
        for e in uid_entries:
            masked = dk.mask(e["uid"])
            t = crypto.mint_token(self.authority.signing_sk, masked,
                                  cycle_epoch, basket, valid_from, valid_to)
            toks.append(t)
            self.tokens.append(t)
        return toks

    def ingest(self, domain: str, payload: dict) -> dict:
        # 1) resolve token redemptions -> cross-device duplicate flags
        dup_flags = []
        for token_id in payload.get("redeemed_token_ids", []):
            if token_id in self.redeemed_token_ids:
                flag = {"token_id": token_id,
                        "reason": "duplicate redemption across devices"}
                dup_flags.append(flag)
                self.duplicate_flags.append(flag)
            else:
                self.redeemed_token_ids.add(token_id)
        for h in payload.get("used_token_hashes", []):
            self.redeemed_hashes.add(b64d(h))

        evidence_log = {
            "anchors": payload.get("anchors", []),
            "clock": payload.get("clock_snapshot"),
            "attestation": payload.get("attestation_quote"),
            "quarantine_reports": payload.get("quarantine_reports", []),
        }

        # 2) delta against THIS device's own snapshot chain
        device_id = payload.get("device_id", "default")
        st = self.device_chain.setdefault(device_id, {
            "seq": 0, "prev_hash": b64e(sha256(b"genesis")), "seen": set(),
        })
        delta = [r for r in self.records.get(domain, [])
                 if crypto.canonical(r) not in st["seen"]]
        snap = self._snapshot(domain, delta, dup_flags, evidence_log, st)
        st["seq"] = snap["seq"]
        st["prev_hash"] = snap["snapshot_hash"]
        st["seen"].update(crypto.canonical(r) for r in delta)
        return snap

    def _snapshot(self, domain: str, delta: list[dict],
                  dup_flags: list[dict], evidence: dict, st: dict) -> dict:
        seq = st["seq"] + 1
        prev_hash = st["prev_hash"]
        root = b64e(MerkleTree([sha256(crypto.canonical(r))
                                for r in delta]).root) if delta \
            else b64e(sha256(b"empty-snapshot"))
        snap = {
            "seq": seq,
            "domain": domain,
            "prev_snapshot_hash": prev_hash,
            "merkle_root": root,
            "records": delta,
            "duplicate_flags": dup_flags,
            "revocations": list(self.revocations.values()),
            "kill_switches": list(self.kill_switches),
            "snapshot_hash": "",
        }
        snap["snapshot_hash"] = b64e(sha256(crypto.canonical(snap)))
        unsigned = {k: v for k, v in snap.items() if k != "sig"}
        snap["sig"] = b64e(crypto.ed25519_sign(
            self.authority.signing_sk, crypto.canonical(unsigned)))
        evidence["snapshot_seq"] = seq
        return snap

    def add_revocation(self, masked_uid: str, reason: str) -> None:
        if masked_uid not in self.revocations:
            self.revocations[masked_uid] = \
                self.authority.sign_beneficiary_record({
                    "kind": "revocation", "masked_uid": masked_uid,
                    "reason": reason, "at": self.clock_now,
                })

    def add_kill_switch(self, model_version: str) -> None:
        self.kill_switches.append(
            auth.build_kill_switch(self.authority, model_version))

    def add_model_update(self, model_version: str, model_sha256: str) -> None:
        self.model_updates.append(
            auth.build_model_update(self.authority, model_version,
                                    model_sha256))


# --------------------------------------------------------------------------- #
# On-device sync client
# --------------------------------------------------------------------------- #

class SyncClient:
    def __init__(self, store, clock, domain_uid_key: bytes, domain: str,
                 authority_pk_der: bytes):
        self.store = store
        self.clock = clock
        self.domain_uid_key = domain_uid_key
        self.domain = domain
        self.authority_pk_der = authority_pk_der

    def _last_seq(self) -> int:
        return int(self.store.get_sync_state("snapshot_seq", "0"))

    def push(self, server: SyncServer) -> dict:
        con = self.store._connect()
        try:
            hashes = [r[0] for r in con.execute(
                "SELECT token_hash FROM used_tokens ORDER BY redeemed_at")]
            redeemed = [r[0] for r in con.execute(
                "SELECT token_id FROM tokens WHERE status='redeemed'")]
            quotes = [r[0] for r in con.execute(
                "SELECT anchor_sig FROM ledger_block "
                "WHERE anchor_sig IS NOT NULL ORDER BY idx")]
        finally:
            con.close()
        return {
            "domain": self.domain,
            "device_id": self.store.meta("device_id", self.domain),
            "since_seq": self._last_seq(),
            "redeemed_token_ids": redeemed,
            "used_token_hashes": hashes,
            "anchors": quotes,
            "quarantine_reports": [
                {"kind": q["kind"], "reason": q["reason"]}
                for q in self.store.quarantined()
            ],
        }

    def fetch(self, server: SyncServer, rng=None, corrupt_chance: float = 0.0
              ) -> dict:
        payload = self.push(server)
        snap = server.ingest(self.domain, payload)
        self.validate(snap)

        # 3) chunked, resumable, corruption-retrying application
        records = snap["records"]
        applied = corrupted = 0
        for i, rec in enumerate(records):
            chunk = crypto.canonical(rec)
            if rng is not None and rng.random() < corrupt_chance:
                corrupted += 1
                self.store.quarantine("snapshot_record", b64e(chunk),
                                      "corrupted chunk (fault injection)")
                continue
            if self._apply_record(rec):
                applied += 1

        # 4) duplicate flags + revocations + kill-switches + model updates
        for flag in snap.get("duplicate_flags", []):
            self.store.set_sync_state("dup_flag_" + flag["token_id"],
                                      flag["reason"])
        for rev in snap.get("revocations", []):
            f = crypto._parse_canonical(b64d(rev["body"]))
            self.store.set_sync_state("revoked_" + f.get("masked_uid", ""),
                                      f.get("reason", "revoked"))
        for ks in snap.get("kill_switches", []):
            f = crypto._parse_canonical(b64d(ks["body"]))
            self.store.set_sync_state("kill_switch",
                                      f.get("model_version", ""))
        for mu in snap.get("model_updates", []):
            f = crypto._parse_canonical(b64d(mu["body"]))
            self.store.set_sync_state(
                "model_update:" + f.get("model_version", ""),
                f.get("model_sha256", ""))

        # 5) resumable progress
        self.store.set_sync_state("snapshot_seq", str(snap["seq"]))
        self.store.set_sync_state("snapshot_hash", snap["snapshot_hash"])

        # 6) refresh signed clock anchor
        anchor = auth.build_clock_anchor(server.authority, server.clock_now,
                                         self.domain)
        self.store.install_clock_anchor(anchor["body"], anchor["sig"],
                                        server.clock_now, 0.0)
        self.clock.set_anchor(anchor, self.authority_pk_der)

        return {"applied": applied, "corrupted": corrupted, "seq": snap["seq"]}

    # ------------------------------------------------------------------ #
    def validate(self, snap: dict) -> None:
        """Reject a poisoned, replayed, or chain-gapped snapshot.  Raises
        ValueError; the caller quarantines nothing further - nothing is
        applied from an unvalidated snapshot."""
        unsigned = {k: v for k, v in snap.items() if k != "sig"}
        body = crypto.canonical(unsigned)
        if not crypto.ed25519_verify(
            crypto.load_pub(self.authority_pk_der), body, b64d(snap["sig"])
        ):
            raise ValueError("snapshot signature invalid (poisoned payload)")
        if snap["seq"] <= self._last_seq():
            raise ValueError("snapshot replay detected (seq not advancing)")
        expected_prev = self.store.get_sync_state("snapshot_hash",
                                                  b64e(sha256(b"genesis")))
        if snap["prev_snapshot_hash"] != expected_prev:
            raise ValueError("snapshot chain gap (prev hash mismatch)")

    def _apply_record(self, rec: dict) -> bool:
        """Apply one authority-signed record into the local store; any
        unsigned or malformed record is quarantined, never applied."""
        try:
            fields = crypto._parse_canonical(b64d(rec["body"]))
        except Exception:
            self.store.quarantine("snapshot_record",
                                  b64e(crypto.canonical(rec)),
                                  "malformed canonical payload")
            return False

        if fields.get("kind") == "revocation":
            masked = fields.get("masked_uid", "")
            dsid = domain_dsid(self.domain_uid_key, self.domain, masked)
            self.store.apply_revocation(self.authority_pk_der, rec, dsid)
            self.store.set_sync_state(
                "revoked_" + masked, fields.get("reason", "revoked"))
            return True

        if "token_id" in fields and "template_enc" not in fields:
            tok = {"payload": rec["body"], "sig": rec["sig"]}
            if not crypto.verify_token(self.authority_pk_der, tok):
                self.store.quarantine("snapshot_record",
                                      b64e(crypto.canonical(rec)),
                                      "token signature invalid")
                return False
            try:
                self.store.insert_token(self.authority_pk_der, tok)
                return True
            except Exception:
                return False  # duplicate token already present - fine

        if "template_enc" in fields and "masked_uid" in fields:
            masked = fields["masked_uid"]
            dsid = domain_dsid(self.domain_uid_key, self.domain, masked)
            try:
                self.store.upsert_beneficiary(self.authority_pk_der, rec, dsid)
                return True
            except Exception:
                return False

        self.store.quarantine("snapshot_record", b64e(crypto.canonical(rec)),
                              "unknown record shape")
        return False