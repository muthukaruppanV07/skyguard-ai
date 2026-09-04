# SPDX-License-Identifier: MIT
"""Entitlement + verification flow tests: the offline decision tree,
PAD gating, fallback locks, grace, four-eyes overrides, timed lockouts and
clock-tamper fail-closed behaviour."""

from __future__ import annotations

import pytest

from pdssec import sync as syncmod
from pdssec.entitlement import EntitlementDenied
from tests.conftest import dsid_of, mint_and_load_tokens


def test_offline_verify_eligible(village, shop):
    dsid = dsid_of(village, 0)
    res = shop.verify_face("op-1", dsid, genuine=True, wall_now=village.now)
    assert res["verdict"] == "eligible"


def test_pad_reject_fails_closed(village, shop):
    dsid = dsid_of(village, 0)
    with pytest.raises(EntitlementDenied) as ei:
        shop.verify_face("op-1", dsid, genuine=True,
                         liveness_kind="printed_photo",
                         liveness_score=0.1, wall_now=village.now)
    assert ei.value.code == "pad_reject"


def test_impostor_match_fail(village, shop):
    dsid = dsid_of(village, 0)
    with pytest.raises(EntitlementDenied) as ei:
        shop.verify_face("op-1", dsid, genuine=False, wall_now=village.now)
    assert ei.value.code == "match_fail"


def test_expired_entitlement_denied(village, shop):
    dsid = dsid_of(village, 0)
    # shrink the signed validity window to the past; secure clock is anchored
    # at village.now, so the eligibility window check must now reject
    con = shop.store._connect()
    con.execute("UPDATE beneficiaries SET valid_to=? WHERE dsid=?",
                (village.now - 1, dsid))
    con.commit()
    con.close()
    with pytest.raises(EntitlementDenied) as ei:
        shop.verify_face("op-1", dsid, genuine=True, wall_now=village.now)
    assert ei.value.code == "expired"


def test_redeem_and_local_double_spend(village, shop, shop2):
    toks = mint_and_load_tokens(village)
    t = toks[0]
    res = shop.redeem(t["token_id"], "op-1")
    assert res["verdict"] == "redeemed"
    # same device same token: denied immediately
    with pytest.raises(EntitlementDenied) as ei:
        shop.redeem(t["token_id"], "op-1")
    assert ei.value.code == "double_spend_local"


def test_grace_issue_allowed_within_band(village, shop):
    dsid = dsid_of(village, 1)
    # shrink validity so the window is recently expired
    con = shop.store._connect()
    con.execute("UPDATE beneficiaries SET valid_to=? WHERE dsid=?",
                (village.now - 3600 * 2, dsid))
    con.commit()
    con.close()
    res = shop.ent.grace_issue(dsid, village.authority.signing_pk_der,
                               "op-1", "missed cycle")
    assert res.allowed
    assert "grace" in res.code


def test_grace_denied_after_redeem(village, shop):
    # grace is for a *genuine* miss: once this person's token is redeemed,
    # grace must be denied (authority resolves cross-shop at sync)
    dk = village.authority.domain_keys(village.domain)
    person = village.beneficiaries[1]
    masked = dk.mask(person["uid"])
    dsid = syncmod.domain_dsid(dk.domain_uid_key, village.domain, masked)
    toks = mint_and_load_tokens(village)
    # find the token minted for this person (same masked uid)
    tok_for_person = next(t for t in toks
                          if t["masked_uid"] == masked)
    shop.redeem(tok_for_person["token_id"], "op-1")
    res = shop.ent.grace_issue(dsid, village.authority.signing_pk_der,
                               "op-1", "missed cycle")
    assert not res.allowed


def test_revoked_beneficiary_denied(village, shop):
    uid = village.revoked_uid
    dk = village.authority.domain_keys(village.domain)
    masked = dk.mask(uid)
    dsid = syncmod.domain_dsid(dk.domain_uid_key, village.domain, masked)
    rec = village.authority.sign_beneficiary_record({
        "kind": "revocation", "masked_uid": masked, "reason": "dup",
    })
    shop.store.apply_revocation(village.authority.signing_pk_der, rec, dsid)
    with pytest.raises(EntitlementDenied) as ei:
        shop.verify_face("op-1", dsid, genuine=True, wall_now=village.now)
    assert ei.value.code in ("revoked", "match_fail")


def test_four_eyes_override_and_rate_limit(village, shop):
    # override requires two distinct operators
    res = shop.override("op-a", "op-b", "subject-x", "family missing ID")
    assert res["verdict"] == "override_issued"
    # same operator pair twice -> rate limit (3 max per shift)
    shop.ent.MAX_OVERRIDE_ATTEMPTS_PER_SHIFT = 1
    with pytest.raises(EntitlementDenied) as ei:
        shop.override("op-a", "op-b", "subject-y", "again")
    assert ei.value.code == "override_rate_limited"
    # same operator both slots is rejected immediately
    with pytest.raises(EntitlementDenied) as ei:
        shop.override("op-a", "op-a", "subject-z", "not four eyes")
    assert ei.value.code == "not_four_eyes"


def test_lockout_after_repeated_failures(village, shop):
    dsid = dsid_of(village, 0)
    for _ in range(shop.ent.LOCKOUT_AFTER_FAILURES):
        try:
            shop.verify_face("bad-op", dsid, genuine=False,
                             wall_now=village.now)
        except EntitlementDenied:
            pass
    lock = shop.ent.check_lockout("bad-op")
    assert not lock.allowed
    assert lock.code == "lockout"


def test_clock_rewind_fails_closed(village, shop):
    dsid = dsid_of(village, 0)
    village.rewind_clock(0, 86400)
    with pytest.raises(Exception) as ei:
        shop.verify_face("op-1", dsid, genuine=True, wall_now=village.now)
    msg = str(ei.value).lower()
    assert any(w in msg for w in ("clock", "tamper", "rewound", "anchor"))


def test_all_verifications_recorded_in_ledger(village, shop):
    before = len(shop.ledger.verify_chain())
    dsid = dsid_of(village, 2)
    shop.verify_face("op-1", dsid, genuine=True, wall_now=village.now)
    with pytest.raises(EntitlementDenied):
        shop.verify_face("op-1", dsid, genuine=False, wall_now=village.now)
    assert len(shop.ledger.verify_chain()) == before  # chain stays healthy
    kinds = [t["kind"] for t in shop.ledger.tail(20)]
    assert "audit" in kinds