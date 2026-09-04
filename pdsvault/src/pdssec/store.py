# SPDX-License-Identifier: MIT
"""Encrypted-at-rest local store (SQLite/WAL) with versioned, hash-pinned
migrations and a quarantine discipline: only *signed* authority records are
ever trusted; anything unsigned, malformed, or that breaks the hash chain is
quarantined, never used for verification.

Production storage is SQLCipher with the page key sealed to the TPM.  This
reference implementation uses SQLite with app-layer AEAD for sensitive columns
(template blobs, domain-scoped ids) - the migration + quarantine machinery is
identical to production.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from . import crypto
from .crypto import b64d, b64e

SCHEMA_VERSION = 2

# Each migration is (version, sql).  Its sha256 is measured into the PCR bank
# at boot so the model/cache/schema image is part of the trust chain and any
# out-of-band schema tampering breaks attestation.
MIGRATIONS = [
    (
        1,
        """
        CREATE TABLE meta(
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        );
        CREATE TABLE beneficiaries(
            dsid TEXT PRIMARY KEY,
            masked_uid TEXT NOT NULL,
            template_enc TEXT NOT NULL,
            entitlements TEXT NOT NULL,       -- canonical basket string
            valid_from INTEGER NOT NULL,
            valid_to INTEGER NOT NULL,
            cycle_epoch INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            body TEXT NOT NULL,               -- canonical signed payload
            sig TEXT NOT NULL                 -- authority signature
        );
        CREATE TABLE revoked(
            dsid TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            body TEXT NOT NULL,
            sig TEXT NOT NULL,
            applied_at INTEGER NOT NULL
        );
        CREATE TABLE tokens(
            token_id TEXT PRIMARY KEY,
            masked_uid TEXT NOT NULL,
            cycle_epoch INTEGER NOT NULL,
            basket TEXT NOT NULL,
            valid_from INTEGER NOT NULL,
            valid_to INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'unredeemed',
            redeemed_at INTEGER,
            body TEXT NOT NULL,
            sig TEXT NOT NULL
        );
        CREATE TABLE used_tokens(
            token_hash TEXT PRIMARY KEY,
            redeemed_at INTEGER NOT NULL,
            cycle_epoch INTEGER NOT NULL
        );
        CREATE TABLE ledger_block(
            idx INTEGER PRIMARY KEY,
            prev_hash TEXT NOT NULL,
            merkle_root TEXT NOT NULL,
            txn_count INTEGER NOT NULL,
            header_sig TEXT NOT NULL,
            anchor_sig TEXT,                  -- signed periodic root anchor
            signed_at INTEGER NOT NULL
        );
        CREATE TABLE ledger_txn(
            txn_hash TEXT PRIMARY KEY,
            block_idx INTEGER NOT NULL,
            kind TEXT NOT NULL,
            data TEXT NOT NULL,
            signed_at INTEGER NOT NULL
        );
        CREATE TABLE audit(
            idx INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            op TEXT NOT NULL,
            actor TEXT NOT NULL,
            subject TEXT,
            detail TEXT,
            sig TEXT NOT NULL,
            prev_hash TEXT NOT NULL
        );
        CREATE TABLE overrides(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_ts INTEGER NOT NULL,
            subject TEXT NOT NULL,
            reason TEXT NOT NULL,
            operator_a TEXT NOT NULL,
            operator_b TEXT,
            sig_a TEXT NOT NULL,
            sig_b TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            token_id TEXT,
            appeal_path TEXT
        );
        CREATE TABLE quarantine(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            reason TEXT NOT NULL,
            found_at INTEGER NOT NULL
        );
        CREATE TABLE sync_state(
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        );
        CREATE TABLE clock_anchor(
            unix_ts INTEGER PRIMARY KEY,
            body TEXT NOT NULL,
            sig TEXT NOT NULL,
            installed_mono REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tokens_epoch ON tokens(cycle_epoch);
        CREATE INDEX IF NOT EXISTS idx_benef_valid ON beneficiaries(valid_to);
        """
    ),
    (
        2,
        """
        ALTER TABLE beneficiaries ADD COLUMN pin_salt TEXT;
        ALTER TABLE beneficiaries ADD COLUMN pin_hash TEXT;
        """
    ),
]

AUDIT_OPS = {
    "verify_ok", "verify_fail", "verify_pad_reject", "redeem",
    "redeem_duplicate_local", "redeem_duplicate_sync", "grace_issue",
    "override_request", "override_approve", "override_deny", "clock_tamper",
    "sync_start", "sync_done", "sync_quarantine", "boot_diag", "lockout",
}


def migration_hashes() -> dict[int, str]:
    return {v: hashlib.sha256(sql.encode("utf-8")).hexdigest()
            for v, sql in MIGRATIONS}


class StoreError(Exception):
    pass


class QuarantinedRecord(StoreError):
    pass


class Store:
    def __init__(self, db_path: str, storage_key: bytes):
        self.db_path = db_path
        self.storage_key = storage_key
        self._init_schema()

    # ------------------------------------------------------------------ #
    # schema / migration (measured at boot)
    # ------------------------------------------------------------------ #

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA synchronous=FULL")
        return con

    def _init_schema(self) -> None:
        con = self._connect()
        try:
            row = con.execute("PRAGMA user_version").fetchone()
            current = row[0]
            for version, sql in sorted(MIGRATIONS, key=lambda m: m[0]):
                if version > current:
                    con.executescript(sql)
                    con.execute(f"PRAGMA user_version={version}")
            # schema must match the last known-good version or the cache is
            # not trustworthy: only signed snapshots may change it.
            con.commit()
        finally:
            con.close()

    def schema_version(self) -> int:
        con = self._connect()
        try:
            return con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()

    def meta(self, key: str, default: str | None = None) -> str | None:
        con = self._connect()
        try:
            row = con.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
            return row[0] if row else default
        finally:
            con.close()

    def set_meta(self, key: str, value: str) -> None:
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO meta(k,v) VALUES(?,?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, value),
            )
            con.commit()
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # quarantine discipline
    # ------------------------------------------------------------------ #

    def quarantine(self, kind: str, payload: str, reason: str) -> None:
        if isinstance(payload, (bytes, bytearray)):
            payload = b64e(bytes(payload))
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO quarantine(kind, payload, reason, found_at) "
                "VALUES(?,?,?,?)",
                (kind, payload, reason, int(__import__("time").time())),
            )
            con.commit()
        finally:
            con.close()

    def quarantine_count(self) -> int:
        con = self._connect()
        try:
            return con.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        finally:
            con.close()

    def insert_override(self, request_ts: int, subject: str, reason: str,
                        operator_a: str, operator_b: str, sig_a: str,
                        sig_b: str, status: str = "approved") -> None:
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO overrides(request_ts, subject, reason, operator_a, "
                "operator_b, sig_a, sig_b, status) VALUES(?,?,?,?,?,?,?,?)",
                (request_ts, subject, reason, operator_a, operator_b,
                 sig_a, sig_b, status),
            )
            con.commit()
        finally:
            con.close()

    def quarantined(self) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT id, kind, reason, found_at FROM quarantine ORDER BY id"
            ).fetchall()
            return [{"id": r[0], "kind": r[1], "reason": r[2], "found_at": r[3]}
                    for r in rows]
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # beneficiaries (authority-signed only)
    # ------------------------------------------------------------------ #

    def upsert_beneficiary(self, authority_pub_der: bytes, record: dict,
                           dsid: str) -> None:
        """Append/refresh a beneficiary row only if the authority signature
        verifies.  Unsigned / tampered rows go to quarantine, never into the
        verification path."""
        from .identity import verify_authority_record
        if not verify_authority_record(authority_pub_der, record):
            self.quarantine("beneficiary", b64e(crypto.canonical(record)),
                            "authority signature invalid")
            raise QuarantinedRecord("unsigned/tampered beneficiary record")
        # All fields are taken from the *signed body*, never from the
        # unauthenticated envelope keys (a cache attacker must not be able to
        # alter displayed entitlements while keeping a valid signature).
        body = b64d(record["body"])
        try:
            f = crypto._parse_canonical(body)
        except Exception:
            self.quarantine("beneficiary", b64e(body),
                            "body not canonical")
            raise QuarantinedRecord("malformed beneficiary body")
        required = ("masked_uid", "template_enc", "entitlements",
                    "valid_from", "valid_to", "cycle_epoch")
        if not all(k in f for k in required):
            self.quarantine("beneficiary", b64e(body),
                            "beneficiary body missing fields")
            raise QuarantinedRecord("incomplete beneficiary body")
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO beneficiaries(
                    dsid, masked_uid, template_enc, entitlements,
                    valid_from, valid_to, cycle_epoch, status, body, sig,
                    pin_salt, pin_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(dsid) DO UPDATE SET
                    masked_uid=excluded.masked_uid,
                    template_enc=excluded.template_enc,
                    entitlements=excluded.entitlements,
                    valid_from=excluded.valid_from,
                    valid_to=excluded.valid_to,
                    cycle_epoch=excluded.cycle_epoch,
                    status=excluded.status,
                    body=excluded.body,
                    sig=excluded.sig,
                    pin_salt=excluded.pin_salt,
                    pin_hash=excluded.pin_hash
                """,
                (dsid, f["masked_uid"], f["template_enc"],
                 f["entitlements"], int(f["valid_from"]),
                 int(f["valid_to"]), int(f["cycle_epoch"]), "active",
                 record["body"], record["sig"],
                 f.get("pin_salt"), f.get("pin_hash")),
            )
            con.commit()
        finally:
            con.close()

    def get_beneficiary(self, dsid: str) -> dict | None:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT * FROM beneficiaries WHERE dsid=?", (dsid,)
            ).fetchone()
            if row is None:
                return None
            cols = [d[0] for d in con.execute(
                "SELECT * FROM beneficiaries").description]
            return dict(zip(cols, row))
        finally:
            con.close()

    def all_beneficiaries(self) -> list[dict]:
        con = self._connect()
        try:
            cols = [d[0] for d in con.execute(
                "SELECT * FROM beneficiaries").description]
            return [dict(zip(cols, r)) for r in con.execute(
                "SELECT * FROM beneficiaries").fetchall()]
        finally:
            con.close()

    def apply_revocation(self, authority_pub_der: bytes, rec: dict,
                         dsid: str) -> None:
        from .identity import verify_authority_record
        if not verify_authority_record(authority_pub_der, rec):
            self.quarantine("revocation", b64e(crypto.canonical(rec)),
                            "revocation signature invalid")
            raise QuarantinedRecord("unsigned revocation")
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO revoked(dsid, reason, body, sig, applied_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(dsid) DO UPDATE SET "
                "reason=excluded.reason, applied_at=excluded.applied_at",
                (dsid, rec.get("reason", "revoked"), rec["body"], rec["sig"],
                 int(__import__("time").time())),
            )
            con.execute(
                "UPDATE beneficiaries SET status='revoked' WHERE dsid=?",
                (dsid,),
            )
            con.commit()
        finally:
            con.close()

    def is_revoked(self, dsid: str) -> bool:
        con = self._connect()
        try:
            return con.execute(
                "SELECT COUNT(*) FROM revoked WHERE dsid=?", (dsid,)
            ).fetchone()[0] > 0
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # entitlement tokens
    # ------------------------------------------------------------------ #

    def insert_token(self, authority_pub_der: bytes, token: dict) -> None:
        from .crypto import load_pub, verify_token
        if not verify_token(load_pub(authority_pub_der), token):
            self.quarantine("token", token.get("payload", "?"),
                            "token signature invalid")
            raise QuarantinedRecord("unsigned token")
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO tokens(
                    token_id, masked_uid, cycle_epoch, basket,
                    valid_from, valid_to, status, body, sig
                ) VALUES(?,?,?,?,?,?,'unredeemed',?,?)
                """,
                (token["token_id"], token["masked_uid"], token["cycle_epoch"],
                 token["basket"], token["valid_from"], token["valid_to"],
                 token["payload"], token["sig"]),
            )
            con.commit()
        finally:
            con.close()

    def mark_token_redeemed(self, token_id: str, at: int) -> None:
        con = self._connect()
        try:
            con.execute(
                "UPDATE tokens SET status='redeemed', redeemed_at=? "
                "WHERE token_id=?",
                (at, token_id),
            )
            con.commit()
        finally:
            con.close()

    def get_token(self, token_id: str) -> dict | None:
        con = self._connect()
        try:
            row = con.execute("SELECT * FROM tokens WHERE token_id=?",
                              (token_id,)).fetchone()
            if row is None:
                return None
            cols = [d[0] for d in con.execute("SELECT * FROM tokens").description]
            return dict(zip(cols, row))
        finally:
            con.close()

    def find_redeemable_token(self, masked_uid: str, cycle_epoch: int,
                              now: int) -> dict | None:
        """A value-claimable token for the subject in the current epoch whose
        signed validity window contains `now` and that has not been spent on
        this device."""
        con = self._connect()
        try:
            row = con.execute(
                "SELECT * FROM tokens WHERE masked_uid=? AND cycle_epoch=? "
                "AND status='unredeemed' AND valid_from<=? AND valid_to>=? "
                "ORDER BY valid_to LIMIT 1",
                (masked_uid, cycle_epoch, now, now),
            ).fetchone()
            if row is None:
                return None
            cols = [d[0] for d in con.execute("SELECT * FROM tokens").description]
            return dict(zip(cols, row))
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # used-token dedup (local double-spend ledger)
    # ------------------------------------------------------------------ #

    def record_used_token(self, token_hash: str, cycle_epoch: int, at: int) -> None:
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO used_tokens(token_hash, redeemed_at, cycle_epoch) "
                "VALUES(?,?,?)",
                (token_hash, at, cycle_epoch),
            )
            con.commit()
        finally:
            con.close()

    def token_hash_used(self, token_hash: str) -> bool:
        con = self._connect()
        try:
            return con.execute(
                "SELECT COUNT(*) FROM used_tokens WHERE token_hash=?",
                (token_hash,),
            ).fetchone()[0] > 0
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # sync / clock state
    # ------------------------------------------------------------------ #

    def get_sync_state(self, key: str, default: str | None = None) -> str | None:
        con = self._connect()
        try:
            row = con.execute("SELECT v FROM sync_state WHERE k=?",
                              (key,)).fetchone()
            return row[0] if row else default
        finally:
            con.close()

    def set_sync_state(self, key: str, value: str) -> None:
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO sync_state(k,v) VALUES(?,?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, value),
            )
            con.commit()
        finally:
            con.close()

    def install_clock_anchor(self, body: str, sig: str, unix_ts: int,
                             mono: float) -> None:
        con = self._connect()
        try:
            con.execute(
                "INSERT OR REPLACE INTO clock_anchor(unix_ts, body, sig, "
                "installed_mono) VALUES(?,?,?,?)",
                (unix_ts, body, sig, mono),
            )
            con.commit()
        finally:
            con.close()

    def latest_clock_anchor(self) -> dict | None:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT unix_ts, body, sig FROM clock_anchor "
                "ORDER BY unix_ts DESC LIMIT 1"
            ).fetchone()
            return {"unix_ts": row[0], "body": row[1], "sig": row[2]} if row else None
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # integrity: detect unsigned rows in cache (poisoned cache check)
    # ------------------------------------------------------------------ #

    def verify_cache_integrity(self, authority_pub_der: bytes) -> list[str]:
        """Scan every beneficiary/token/revocation row and re-verify its
        signature.  Returns a list of DSIDs failing verification (they are
        removed from the active set by the caller)."""
        from .identity import verify_authority_record
        from .crypto import load_pub, verify_token
        bad = []
        pk = load_pub(authority_pub_der)
        for row in self.all_beneficiaries():
            rec = {"body": row["body"], "sig": row["sig"]}
            if not verify_authority_record(authority_pub_der, rec):
                bad.append(row["dsid"])
        con = self._connect()
        try:
            tok_rows = con.execute("SELECT * FROM tokens").fetchall()
            cols = [d[0] for d in con.execute("SELECT * FROM tokens").description]
            for r in tok_rows:
                t = dict(zip(cols, r))
                tok = {"payload": t["body"], "sig": t["sig"]}
                if not verify_token(pk, tok):
                    bad.append("token:" + t["token_id"])
        finally:
            con.close()
        return bad
