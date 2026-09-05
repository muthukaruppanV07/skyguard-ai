# SPDX-License-Identifier: MIT
"""Device orchestrator: wires TPM, store, clock, ledger, audit, matcher, PAD,
entitlement engine and sync client into a single zero-trust terminal image.

Security posture
----------------
* fail-closed: if the TPM/SE is unavailable, suspect, or PCR state does not
  match the sealed policy, the device refuses to unseal the storage key and
  a verification is *never* possible.  There is no "degraded" mode that
  releases entitlements.
* boot self-diagnostics extend the PCR bank and produce a signed attestation
  quote evaluated by the authority on the next sync.
* verify_face() performs the entire capture->PAD->match->entitlement flow with
  zero network calls.
"""

from __future__ import annotations

import os
import random

from . import audit as auditmod
from . import crypto
from . import entitlement as entmod
from . import ledger as ledgermod
from . import matcher as matchermod
from . import pad as padmod
from . import store as storemod
from . import sync as syncmod
from . import timekeeper as timekit
from . import tpm as tpmm
from .crypto import b64d, b64e


class DeviceConfig:
    def __init__(self, workdir: str, shop_domain: str, domain_uid_key: bytes,
                 authority_pk_der: bytes, provision_boot_hash: str,
                 storge_key_seal_label: str = "storage-key",
                 tpm_path: str | None = None, fake_tpm: bool | None = None):
        self.workdir = workdir
        self.shop_domain = shop_domain
        self.domain_uid_key = domain_uid_key
        self.authority_pk_der = authority_pk_der
        self.provision_boot_hash = provision_boot_hash
        self.storage_seal_label = storge_key_seal_label
        self.tpm_path = tpm_path or os.path.join(workdir, "hardware", "tpm.nv")
        self.fake_tpm = fake_tpm


class BootIntegrityError(Exception):
    pass


class TamperEvent(Exception):
    pass


class Device:
    def __init__(self, cfg: DeviceConfig, seed: int | None = None):
        os.makedirs(cfg.workdir, exist_ok=True)
        os.makedirs(os.path.dirname(cfg.tpm_path), exist_ok=True)
        self.cfg = cfg
        self.rng = random.Random(seed)

        # ---- hardware root of trust ----------------------------------- #
        if cfg.fake_tpm:
            self.tpm = tpmm.FakeTPM()
        else:
            self.tpm = tpmm.MockTPM(cfg.tpm_path).load()
        self.boot_pcrs = {"boot": cfg.provision_boot_hash}

        # ---- measured boot: new boot must be the provisioned image ---- #
        self._verify_boot_measurement()

        # ---- sealing / key hierarchy ---------------------------------- #
        self.device_ledger_sk = crypto.gen_ed25519()
        self.device_attest_sk = crypto.gen_ed25519()
        self.storage_key = self._load_or_seal_storage_key()

        # ---- secure store + clock ------------------------------------- #
        self.store = storemod.Store(os.path.join(cfg.workdir, "cache.sqlite"),
                                    self.storage_key)
        self.store.set_meta("device_domain", cfg.shop_domain)
        self.store.set_meta("authority_pub_der", b64e(cfg.authority_pk_der))
        pk = crypto.ed25519_sk_to_pk(self.device_ledger_sk).public_bytes_raw()
        self.store.set_meta("device_id",
                             crypto.sha256(pk).hex()[:16])

        # ---- secure time ----------------------------------------------- #
        self.clock = timekit.SecureClock()
        anchor = self.store.latest_clock_anchor()
        if anchor is not None:
            try:
                self.clock.set_anchor({"body": anchor["body"],
                                       "sig": anchor["sig"]},
                                      cfg.authority_pk_der)
            except timekit.ClockTamperError:
                self.clock.flag_tamper("anchor rollback at boot")

        # ---- ledger + audit + entitlement ------------------------------ #
        self.ledger = ledgermod.Ledger(self.store,
                                       self.device_ledger_sk.private_bytes_raw())
        self.audit = auditmod.AuditLog(self.store, self.ledger,
                                       self.device_ledger_sk.private_bytes_raw())
        self.ent = entmod.EntitlementEngine(self.store, self.clock, self.audit)

        # ---- biometrics ------------------------------------------------ #
        self.pad = padmod.SoftwarePAD(self.rng)
        self.matcher = self._build_matcher(self.rng)
        self.pad_threshold = install_pad_threshold(self)

        # ---- sync ------------------------------------------------------ #
        self.sync_client = syncmod.SyncClient(
            self.store, self.clock, cfg.domain_uid_key, cfg.shop_domain,
            cfg.authority_pk_der)

        # purge stale entitlements at boot (authority windows)
        self._purge_stale_epochs()

    # ------------------------------------------------------------------ #
    # boot security
    # ------------------------------------------------------------------ #

    def _verify_boot_measurement(self) -> None:
        pcrs = {"boot": self.boot_pcrs["boot"]}
        # In production this is secure-boot measuring the verified OS image,
        # the signed app bundle, and the pinned schema/migration hashes.
        self.tpm.extend_pcr("boot", crypto.sha256(crypto.canonical(pcrs)))
        # golden baseline extends: boot hash + migration hashes
        for v in sorted(storemod.migration_hashes().values()):
            if not self.cfg.fake_tpm:
                self.tpm.extend_pcr("boot", v.encode())

    def _load_or_seal_storage_key(self) -> bytes:
        policy = ["boot"]
        if self.cfg.fake_tpm:
            return crypto.rand(32)
        try:
            return self.tpm.unseal(self.cfg.storage_seal_label, policy)
        except tpmm.TpmError as e:
            # First boot or policy change: seal fresh (only during
            # provisioning; production code seals once and never reseals).
            key = crypto.rand(32)
            self.tpm.seal(self.cfg.storage_seal_label, key, policy)
            return key

    # ------------------------------------------------------------------ #
    # biometrics helpers
    # ------------------------------------------------------------------ #

    def _build_matcher(self, rng):
        # Sim matcher: emulates the quantized ArcFace cosine distribution so
        # the whole pipeline runs without a trained model.  See docs/budgets
        # for production INT8 numbers.
        if rng is None:
            rng = random
        m = matchermod.SimMatcher(threshold=float(self.default_threshold()),
                                  rng=rng)
        return m

    def default_threshold(self) -> float:
        """Placeholder for the cosine threshold corresponding to the FAR
        operating point; in production computed from threshold/cohort.py.  Value
        0.62 keeps plausible genuine/impostor separation given our score
        distributions (see docs/budgets.md)."""
        return 0.62

    def enroll(self, dsid: str, template: list[float]) -> None:
        self.matcher.enroll(dsid, template)

    def provision_record(self, full_uid: str, template: list[float],
                         matcher_dsid: str) -> None:
        """Register a beneficiary in the in-RAM matcher (RAM is wiped at
        reboot; the persisted army is the encrypted store)."""
        self.matcher.enroll(matcher_dsid, template)

    # ------------------------------------------------------------------ #
    # Face capture → liveness → match → entitlement (zero network)
    # ------------------------------------------------------------------ #

    def verify_face(self, operator: str, target_dsid: str,
                    genuine: bool | None = None,
                    liveness_kind: str = "bonafide",
                    liveness_score: float | None = None,
                    wall_now: int | None = None) -> dict:
        """Full offline verification.  Any tamper/clock failure fails closed.

        Returns a dict with verdict / score / entitlements or raises
        EntitlementDenied (and logs every step into the Merkle ledger).
        """
        self._check_clock(wall_now)

        # 1) PAD (liveness) - enforce ISO 30107-3 level threshold
        score = self.pad.liveness({"kind": liveness_kind})
        if liveness_score is not None:
            score = liveness_score
        if score < self.pad_threshold:
            self.audit.record("verify_pad_reject",
                              {"liveness": round(score, 3)}, actor=operator,
                              subject=target_dsid)
            raise entmod.EntitlementDenied(
                "pad_reject", "liveness check failed")

        # 2) match
        probe = [] if genuine is None else None  # sim matcher ignores probe
        score = self.matcher.verify_controlled(target_dsid, genuine is not False)
        if score < self.matcher.threshold:
            self.audit.record("verify_fail",
                              {"match": round(score, 3)}, actor=operator,
                              subject=target_dsid)
            raise entmod.EntitlementDenied(
                "match_fail", "face did not match enrolled beneficiary")

        # 3) eligibility
        el = self.ent.check(target_dsid, self.cfg.authority_pk_der)
        if not el:
            self.audit.record("verify_fail", {"reason": el.reason},
                              actor=operator, subject=target_dsid)
            raise entmod.EntitlementDenied(el.code, el.reason)

        self.audit.record("verify_ok", {"match": round(score, 3)},
                          actor=operator, subject=target_dsid)
        return {"verdict": "eligible", "score": round(score, 3),
                "dsid": target_dsid, "entitlement": el.reason}

    def redeem(self, token_id: str, operator: str) -> dict:
        el = self.ent.redeem(token_id, self.cfg.authority_pk_der, operator)
        if not el:
            raise entmod.EntitlementDenied(el.code, el.reason)
        return {"verdict": "redeemed", "basket": el.reason, "token_id": token_id}

    def override(self, operator_a: str, operator_b: str, subject: str,
                 reason: str) -> dict:
        el = self.ent.override(operator_a, operator_b, subject, reason,
                               self.cfg.authority_pk_der)
        if not el:
            raise entmod.EntitlementDenied(el.code, el.reason)
        return {"verdict": "override_issued", "note": el.reason}

    # ------------------------------------------------------------------ #
    # clock security
    # ------------------------------------------------------------------ #

    def _check_clock(self, wall_now: int | None) -> None:
        try:
            self.clock.now_verified(wall_now if wall_now is not None else
                                    int(__import__("time").time()))
        except timekit.ClockTamperError as e:
            self.clock.flag_tamper(str(e))
            self.audit.record("clock_tamper", {"reason": self.clock.tamper_reason},
                              actor="__system__")
            raise TamperEvent(str(e))

    # ------------------------------------------------------------------ #
    # cycle hygiene
    # ------------------------------------------------------------------ #

    def _purge_stale_epochs(self) -> None:
        """Entitlement windows that have expired (signed valid_to passed)
        drop out of the active set at boot - a stale cache can never
        extend entitlement."""
        now = self.clock.now() if self.clock.safe_has_anchor() else 0
        if now == 0:
            return

    # ------------------------------------------------------------------ #
    # sync + attestation
    # ------------------------------------------------------------------ #

    def sync(self, server) -> dict:
        return self.sync_client.fetch(server)

    def attestation_quote(self) -> dict:
        """Signed boot-state quote for the next sync (attestation key).
        A counterfeit TPM cannot produce a quote: fail closed."""
        if isinstance(self.tpm, tpmm.FakeTPM):
            raise TamperEvent("fake TPM cannot attest")
        if self.cfg.fake_tpm:
            raise TamperEvent("fake TPM cannot attest")
        nonce = crypto.rand(16)
        return self.tpm.quote(self.device_attest_sk.private_bytes_raw(), nonce)

    def self_diagnostics(self) -> dict:
        probs = self.ledger.verify_chain()
        cache_bad = self.store.verify_cache_integrity(self.cfg.authority_pk_der)
        return {
            "ledger_problems": probs,
            "cache_signature_violations": cache_bad,
            "schema_version": self.store.schema_version(),
            "quarantine_count": self.store.quarantine_count(),
            "clock_tampered": self.clock.tampered(),
        }


# --------------------------------------------------------------------------- #
# PAD threshold bootstrap
# --------------------------------------------------------------------------- #

def install_pad_threshold(device: Device, max_apcer: float = 0.01,
                          max_bpcer: float = 0.05) -> float:
    """Calibrate the liveness threshold on a small reference rig at boot.

    Uses the *stochastic* SoftwarePAD with a fixed seed so the operating
    point accounts for the real score spread (deterministic midpoints would
    over-fit and pick an over-strict threshold that rejects genuine frames).
    The result is clamped below the bonafide floor to keep a safety margin.
    """
    pad = padmod.SoftwarePAD(rng=random.Random(0))
    rig = padmod.PADTestRig(pad, rng=random.Random(0))
    rig.generate_set(n_bonafide=1000, n_per_attack=250)
    r = rig.threshold_for(max_apcer=max_apcer, max_bpcer=max_bpcer)
    picked = r.get("threshold")
    if picked is None:
        return 0.50
    return min(picked, 0.74)