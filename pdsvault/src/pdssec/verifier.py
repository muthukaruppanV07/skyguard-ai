# SPDX-License-Identifier: MIT
"""Verification orchestrator - the only component that releases an
entitlement.

Flow (all offline, fail-closed):
    device-health (TPM + clock)         -- else REFUSE
    cache look-up by DSID               -- missing => escalation (NOT_IN_CACHE)
    revoked / expired entitlement        -- REFUSE + log
    PAD liveness gate                    -- attack => PAD_REJECT + lock a strike
    face match (primary)                 -- score vs tiered threshold
    fusion fallbacks: fingerprint, pin   -- per-channel FAR/FRR + abuse limits
    entitlement token                     -- validated (sig + epoch + window),
                                            provisionally redeemed w/ dedup
    every step appends a signed, Merkle-rooted ledger txn.

Human override path: not-in-cache / expired / duplicate are escalated; quota
release requires dual-operator (four-eyes) approval, itself signed,
rate-limited, and logged.
"""

from __future__ import annotations

from . import crypto
from .crypto import b64d
from .store import AUDIT_OPS
from .timekeeper import ClockTamperError
from .ledger import ChainGapError


class VerificationError(Exception):
    pass


class VerificationResult(dict):
    """Enriched dict: ok, reason, path, dsid, masked_uid, ts, token_id,
    attempts_left, override_required."""


class Verifier:
    def __init__(self, store, clock, tpm, ledger, matcher, pad_gate,
                 fusion, lockout, operator_id: str, authority_pk_der: bytes,
                 current_epoch: int, domain_keys, operator_keys: dict | None = None):
        self.store = store
        self.clock = clock
        self.tpm = tpm
        self.ledger = ledger
        self.matcher = matcher
        self.pad_gate = pad_gate
        self.fusion = fusion
        self.lockout = lockout
        self.operator_id = operator_id
        self.authority_pk = crypto.load_pub(authority_pk_der)
        self.current_epoch = current_epoch
        self.domain_keys = domain_keys
        self.operator_keys = {k: crypto.load_pub(v)
                              for k, v in (operator_keys or {}).items()}

    # ------------------------------------------------------------------ #
    # main entry
    # ------------------------------------------------------------------ #

    def verify(self, dsid: str, capture_features: dict,
               query_template: bytes | None,
               fp_accepted: bool | None = None,
               pin: str | None = None) -> VerificationResult:
        subject = f"subject:{dsid}"
        if self.lockout.is_locked(subject):
            return self._fail(dsid, "lockout",
                              f"locked {self.lockout.lockout_remaining_s(subject)}s")
        try:
            self._health_gate()
        except VerificationError as e:
            return self._fail(dsid, "device_untrusted", str(e))

        bh = self.store.get_beneficiary(dsid)
        if bh is None:
            self._log("verify_fail", {"dsid": dsid, "why": "not_in_cache"})
            return self._fail(dsid, "not_in_cache",
                              "not in signed cache - escalated",
                              override_required=True)
        if self.store.is_revoked(dsid):
            self._log("verify_fail", {"dsid": dsid, "why": "revoked"})
            return self._fail(dsid, "revoked", "subject revoked")

        now = self._trusted_now()
        if not (bh["valid_from"] <= now <= bh["valid_to"]):
            self._log("verify_fail", {"dsid": dsid, "why": "entitlement_expired"})
            return self._fail(dsid, "entitlement_expired",
                              f"window [{bh['valid_from']},{bh['valid_to']}] "
                              f"misses now={now}", override_required=True)

        # -- PAD gate --------------------------------------------------- #
        pad = self.pad_gate.evaluate(capture_features)
        if not pad.live:
            self.lockout.record_failure(subject, max_attempts=3)
            self._log("verify_pad_reject",
                      {"dsid": dsid, "score": pad.score, "reasons": pad.reasons})
            return self._fail(dsid, "pad_reject",
                              f"presentation attack suspected: {pad.reasons}")

        # -- biometric fusion ------------------------------------------- #
        decision = {"ok": False, "path": [], "reason": ""}
        face = {"accepted": False}
        if query_template is not None:
            try:
                enrolled = self.domain_keys.decrypt_template(bh["template_enc"])
                face = self.matcher.match(query_template, enrolled,
                                          threshold=self.fusion.face_threshold)
            except Exception as e:
                return self._fail(dsid, "internal", f"matching error: {e}")
        fp = {"accepted": bool(fp_accepted)} if self.fusion.fingerprint_present else None
        pin_ok = None
        if pin is not None:
            pin_ok = self._verify_pin(bh, pin)
        decision = self.fusion.decide(face, fp, pin_ok)

        if not decision["ok"]:
            self.lockout.record_failure(subject, max_attempts=3)
            self._log("verify_fail", {"dsid": dsid, "why": "no_channel_passed",
                                      "path": decision["path"]})
            return self._fail(dsid, "no_channel_passed",
                              f"channels failed: {decision['reason']}",
                              attempts_left=self._attempts_left(subject))
        self.lockout.record_success(subject)

        # -- entitlement token ------------------------------------------ #
        tok = self._redeem_entitlement(bh["masked_uid"], now)
        if tok is None:
            self._log("verify_fail", {"dsid": dsid, "why": "no_token",
                                      "path": decision["path"]})
            return self._fail(dsid, "no_token", "no value token for this epoch",
                              override_required=True)

        self._log("verify_ok", {"dsid": dsid, "path": decision["path"],
                                "token": tok["token_id"]})
        return VerificationResult(
            ok=True, reason="verified", path=decision["path"], dsid=dsid,
            masked_uid=bh["masked_uid"], ts=now, token_id=tok["token_id"],
            attempts_left=None, override_required=False,
        )

    # ------------------------------------------------------------------ #
    # entitlement redemption + dedup (offline-first, provisional)
    # ------------------------------------------------------------------ #

    def _redeem_entitlement(self, masked_uid: str, now: int) -> dict | None:
        tok = self.store.find_redeemable_token(masked_uid, self.current_epoch, now)
        if tok is None:
            return None
        tok_doc = {"payload": tok["body"], "sig": tok["sig"]}
        if not self._verify_token_sig(tok_doc):
            self.store.quarantine("token", tok["body"], "signature invalid at redeem")
            return None
        token_hash = b64e(crypto.sha256(b"tok-spend/v1" + b64d(tok["body"])))
        if self.store.token_hash_used(token_hash) or tok["status"] == "redeemed":
            self._log("redeem_duplicate_local", {"token": tok["token_id"]})
            return None
        self.store.record_used_token(token_hash, tok["cycle_epoch"], now)
        self.store.mark_token_redeemed(tok["token_id"], now)
        self._log("redeem", {"token": tok["token_id"], "basket": tok["basket"]})
        return tok

    def _verify_token_sig(self, tok_doc: dict) -> bool:
        try:
            return crypto.ed25519_verify(
                self.authority_pk, b64d(tok_doc["payload"]), b64d(tok_doc["sig"]))
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # dual-operator (four-eyes) override
    # ------------------------------------------------------------------ #

    def four_eyes_approve(self, subject: str, reason: str, ts: int,
                          op_a: str, sig_a: str, op_b: str, sig_b: str) -> dict:
        key = f"override:{subject}"
        if self.lockout.is_locked(key):
            return {"ok": False, "why": "rate_limited",
                    "remaining": self.lockout.lockout_remaining_s(key)}
        if op_a == op_b or (set([op_a, op_b]) - set(self.operator_keys)):
            return {"ok": False, "why": "operator_identity_rejected"}
        msg = crypto.canonical({"subject": subject, "reason": reason, "ts": ts})
        ok_a = crypto.ed25519_verify(self.operator_keys[op_a], msg, b64d(sig_a))
        ok_b = crypto.ed25519_verify(self.operator_keys[op_b], msg, b64d(sig_b))
        if not (ok_a and ok_b):
            self.lockout.record_failure(key, max_attempts=3, lockout_s=600)
            return {"ok": False, "why": "signature_invalid"}
        self.lockout.record_success(key)
        self.store.insert_override(ts, subject, reason, op_a, op_b, sig_a, sig_b)
        self._log("override_approve", {"subject": subject, "reason": reason,
                                       "ops": [op_a, op_b]})
        return {"ok": True, "why": "four-eyes approval given"}

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    def _health_gate(self) -> None:
        if getattr(self.tpm, "VERSION", "").startswith("fake"):
            raise VerificationError("TPM not trustworthy (fake/counterfeit)")
        if self.clock.tampered():
            raise VerificationError(f"clock tampered: {self.clock.tamper_reason}")
        try:
            self.clock.now()
        except ClockTamperError as e:
            raise VerificationError(str(e))

    def _trusted_now(self) -> int:
        return self.clock.now()

    def _verify_pin(self, bh: dict, pin: str) -> bool:
        if not bh.get("pin_hash") or not bh.get("pin_salt"):
            return False
        from .bio import PinVerifier
        return PinVerifier().verify(pin, b64d(bh["pin_salt"]), b64d(bh["pin_hash"]))

    def _attempts_left(self, subject: str) -> int | None:
        return None

    def _fail(self, dsid, reason, why, attempts_left=None,
              override_required=False) -> VerificationResult:
        return VerificationResult(
            ok=False, reason=reason, why=why, dsid=dsid, path=[],
            masked_uid=None, ts=None, token_id=None,
            attempts_left=attempts_left, override_required=override_required,
        )

    def _log(self, kind: str, data: dict) -> None:
        if kind not in AUDIT_OPS:
            kind = "audit"
        try:
            self.ledger.append(kind, data)
        except ChainGapError as e:
            raise VerificationError(f"ledger chain gap - escalate: {e}")