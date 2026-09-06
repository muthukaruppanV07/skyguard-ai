# SPDX-License-Identifier: MIT
"""Store tests: schema migrations, quarantine, poison-cache detection,
signed-only writes, revocation handling."""

from __future__ import annotations

import tempfile

import pytest

from pdssec import crypto
from pdssec.store import SCHEMA_VERSION, Store, QuarantinedRecord, migration_hashes
from pdssec.sync import domain_dsid


def make_store() -> Store:
    return Store(tempfile.mktemp(prefix="store-"), crypto.rand(32))


def test_migrations_run_to_latest():
    s = make_store()
    assert s.schema_version() == SCHEMA_VERSION
    assert set(migration_hashes()) >= {1, 2}


def test_unsigned_beneficiary_quarantined(authority_pub):
    s = make_store()
    with pytest.raises(QuarantinedRecord):
        s.upsert_beneficiary(authority_pub,
                             {"body": crypto.b64e(b"x"), "sig": crypto.b64e(b"y")},
                             "dsid1")
    assert s.quarantine_count() == 1
    assert s.get_beneficiary("dsid1") is None


def test_signed_beneficiary_applied(village):
    s = make_store()
    ben = village.server.records[village.domain][0]
    fields = crypto._parse_canonical(crypto.b64d(ben["body"]))
    dsid = domain_dsid(village.authority.domain_keys(village.domain)
                       .domain_uid_key, village.domain, fields["masked_uid"])
    s.upsert_beneficiary(village.authority.signing_pk_der, ben, dsid)
    assert s.get_beneficiary(dsid)["status"] == "active"
    assert s.verify_cache_integrity(village.authority.signing_pk_der) == []


def test_poisoned_cache_signature_detected(village, shop):
    # note: village fixture uses DeviceStore with WAL; we poke via simulator
    person0 = village.beneficiaries[0]
    dk = village.authority.domain_keys(village.domain)
    masked = dk.mask(person0["uid"])
    dsid = domain_dsid(dk.domain_uid_key, village.domain, masked)
    village.poke_signature(0, dsid)
    bad = shop.store.verify_cache_integrity(village.authority.signing_pk_der)
    assert dsid in bad


def test_quarantine_rows_listed():
    s = make_store()
    s.quarantine("test", "payload", "because")
    rows = s.quarantined()
    assert len(rows) == 1 and rows[0]["kind"] == "test"


def test_revocation_applies_and_blocks(shop, village):
    uid = village.revoked_uid
    dk = village.authority.domain_keys(village.domain)
    masked = dk.mask(uid)
    dsid = domain_dsid(dk.domain_uid_key, village.domain, masked)
    rec = village.authority.sign_beneficiary_record({
        "kind": "revocation", "masked_uid": masked, "reason": "test",
    })
    shop.store.apply_revocation(village.authority.signing_pk_der, rec, dsid)
    assert shop.store.is_revoked(dsid)
    assert shop.store.get_beneficiary(dsid)["status"] == "revoked"


def test_token_insert_and_lookup(village):
    s = make_store()
    t = crypto.mint_token(village.authority.signing_sk, "m", 1, "wheat", 1, 2)
    s.insert_token(village.authority.signing_pk_der, t)
    got = s.get_token(t["token_id"])
    assert got["status"] == "unredeemed"
    s.mark_token_redeemed(t["token_id"], 5)
    assert s.get_token(t["token_id"])["status"] == "redeemed"


def test_used_token_local_spend(village):
    s = make_store()
    t = crypto.mint_token(village.authority.signing_sk, "m", 1, "wheat", 1, 2)
    th = crypto.b64e(crypto.sha256(crypto.b64d(t["payload"])))
    assert not s.token_hash_used(th)
    s.record_used_token(th, 1, 5)
    assert s.token_hash_used(th)


@pytest.fixture(scope="session")
def authority_pub():
    from pdssec.identity import Authority
    return Authority.generate().signing_pk_der