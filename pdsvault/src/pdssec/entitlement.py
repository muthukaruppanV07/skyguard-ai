# SPDX-License-Identifier: MIT
"""Offline entitlement engine.

Decision tree for a single verification + redemption at a shop with zero
network calls:

  capture → liveness(PAD) → face match → within validity window?
  → revoked? → token valid? → token used on THIS device? → provisionally
  redeem → tolerate → log everything to the Merkle ledger.

Uniqueness across shops is *not* decidable offline: the device provisionally
redeems, records the token hash in its local used-token ledger, and the
central authority resolves doubles at the next sync (chargeback + follow-up
revocation of the second redemption).  Grace for genuinely missed cycles is a
separate authority-minted token; an attempt to double-spend the same token on
the same device is denied immediately.

Overrides (edge cases: not-in-cache / expired / suspect duplicate) are the
emergency exit: they require a signed reason, are rate-limited per operator,
and quota release requires dual-operator (four-eyes) approval - which is
itself written into the Merkle ledger.
"""

from __future__ import annotations

from . import crypto
from .crypto import b64d, b64e, sha256


class EntitlementDenied(Exception):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


class Eligibility:
    def __init__(self, allowed: bool, reason: str = "", code: str = ""):
        self.allowed = allowed
        self.reason = reason
        self.code = code

    def __bool__(self):
        return self.allowed


class EntitlementEngine:
    MAX_OVERRIDE_ATTEMPTS_PER_SHIFT = 3
    LOCKOUT_AFTER_FAILURES = 5

    def __init__(self, store, clock, audit):
        self.store = store
        self.clock = clock
        self.audit = audit

    # ------------------------------------------------------------------ #
    # eligibility check (post match, pre redemption)
    # ------------------------------------------------------------------ #

    def check(self, dsid: str, authority_pub_der: bytes) -> Eligibility:
        ben = self.store.get_beneficiary(dsid)
        if ben is None:
            return Eligibility(False, "beneficiary not in cache",
                               "not_in_cache")
        # point-of-use signature re-verification: a poisoned cache row must
        # never be served, even if the attacker only flipped envelope bytes.
        from .identity import verify_authority_record
        if not verify_authority_record(
                authority_pub_der, {"body": ben["body"], "sig": ben["sig"]}):
            self.store.quarantine("beneficiary_use", ben["body"],
                                  "signature failed at point of use")
            return Eligibility(False, "cache row failed signature check",
                               "tampered_cache")
        if ben["status"] == "revoked" or self.store.is_revoked(dsid):
            return Eligibility(False, "beneficiary revoked", "revoked")
        now = self.clock.now()
        if now < ben["valid_from"] or now > ben["valid_to"]:
            return Eligibility(False,
                               f"entitlement window expired "
                               f"({ben['valid_from']}..{ben['valid_to']})",
                               "expired")
        return Eligibility(True)

    # ------------------------------------------------------------------ #
    # redemption
    # ------------------------------------------------------------------ #

    def redeem(self, token_id: str, authority_pub_der: bytes,
               operator: str) -> Eligibility:
        t = self.store.get_token(token_id)
        if t is None:
            return Eligibility(False, "token not in cache", "not_in_cache")
        tok = {"payload": t["body"], "sig": t["sig"]}
        if not crypto.verify_token(crypto.load_pub(authority_pub_der), tok):
            return Eligibility(False, "token signature invalid", "bad_token")
        now = self.clock.now()
        if now < t["valid_from"] or now > t["valid_to"]:
            return Eligibility(False, "token outside validity window", "expired")

        # 1) local double-spend: same token redeemed on this device before
        t_hash = b64e(sha256(b64d(t["body"])))
        if self.store.token_hash_used(t_hash):
            self.audit.record("redeem_duplicate_local",
                              {"token_id": token_id, "operator": operator},
                              actor=operator, subject=token_id)
            return Eligibility(False, "token already redeemed on this device",
                               "double_spend_local")

        # 2) provisional redemption (uniqueness resolved centrally at sync)
        if t["status"] != "unredeemed":
            return Eligibility(False, "token already provisionally redeemed",
                               "double_spend_local")
        self.store.mark_token_redeemed(token_id, now)
        self.store.record_used_token(t_hash, t["cycle_epoch"], now)
        self.audit.record("redeem",
                          {"token_id": token_id, "basket": t["basket"],
                           "operator": operator},
                          actor=operator, subject=token_id)
        return Eligibility(True, t["basket"], "ok")

    # ------------------------------------------------------------------ #
    # grace / missed-cycle handling
    # ------------------------------------------------------------------ #

    def grace_issue(self, dsid: str, authority_pub_der: bytes,
                    operator: str, reason: str) -> Eligibility:
        """Grace basket for a beneficiary who genuinely missed the window.

        Denied unless (a) the beneficiary is otherwise eligible and within a
        recent expired band, and (b) no redemption for their token hash exists
        on this device (the authority resolves cross-shop duplicates at sync
        and may charge back).
        """
        ben = self.store.get_beneficiary(dsid)
        if ben is None:
            return Eligibility(False, "not in cache; cannot grant grace",
                               "not_in_cache")
        now = self.clock.now()
        expired_recently = (now - ben["valid_to"]) <= 3600 * 24 * 7
        if now < ben["valid_from"]:
            return Eligibility(False, "entitlement not yet started", "too_early")
        if not expired_recently:
            return Eligibility(False, "window not recently expired; "
                               "no grace without authority token", "grace_denied")
        toks = self.store._connect().execute(
            "SELECT body FROM tokens WHERE masked_uid=? AND status='redeemed'",
            (ben["masked_uid"],),
        ).fetchall()
        redeemed_any = any(self.store.token_hash_used(
            b64e(sha256(b64d(r[0])))) for r in toks)
        if redeemed_any:
            return Eligibility(False, "already redeemed; look up the "
                               "authority receipt instead", "already_redeemed")
        self.audit.record("grace_issue",
                          {"dsid": dsid, "operator": operator,
                           "reason": reason},
                          actor=operator, subject=dsid)
        return Eligibility(True, "grace basket", "grace")

    # ------------------------------------------------------------------ #
    # dual-operator override (four-eyes) - emergency edge cases
    # ------------------------------------------------------------------ #

    def override(self, operator_a: str, operator_b: str, subject: str,
                 reason: str, authority_pub_der: bytes) -> Eligibility:
        """Four-eyes quota release for a not-in-cache / suspect-duplicate case.

        Rate-limited: an operator may trigger at most MAX_OVERRIDE_ATTEMPTS
        per device per shift; both operators' signatures go into the ledger.
        The override is provisional - the authority audits every override at
        sync and can revoke + charge back a fraudulent one.
        """
        if operator_a == operator_b:
            return Eligibility(False, "override requires two distinct "
                               "operators", "not_four_eyes")
        count = self.audit.count_operator_overrides(operator_a)
        if count >= self.MAX_OVERRIDE_ATTEMPTS_PER_SHIFT:
            return Eligibility(False, "override rate limit reached",
                               "override_rate_limited")
        rec = self.audit.four_eyes(subject, reason, operator_a, operator_b)
        if not rec.approved:
            return Eligibility(False, "second operator declined", "override_denied")
        return Eligibility(True, f"override issued (provisional) [{subject}]",
                           "override")

    # ------------------------------------------------------------------ #
    # lockout
    # ------------------------------------------------------------------ #

    def check_lockout(self, actor: str) -> Eligibility:
        failures = self.audit.recent_failures(actor, window_s=3600)
        if failures >= self.LOCKOUT_AFTER_FAILURES:
            return Eligibility(False, "operator locked out after repeated "
                               "failed verifications", "lockout")
        return Eligibility(True)