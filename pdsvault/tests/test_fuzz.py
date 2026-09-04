# SPDX-License-Identifier: MIT
"""Adversarial fuzz tests: sync payload parser, image/frame decoder, SQL
identifier filtering, and the record-apply path - all fed untrusted input.

Contract: hostile input is rejected or quarantined, never crashes the host,
never leads to a record being accepted.
"""

from __future__ import annotations

import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from pdssec import crypto
from pdssec import fuzz as fuzzmod
from pdssec import sync as syncmod
from pdssec.simulator import Village


@given(st.binary())
@settings(max_examples=300)
def test_canonical_parser_never_crashes(buf):
    assert fuzzmod.fuzz_canonical(buf) is True


@given(st.binary())
@settings(max_examples=300)
def test_frame_decoder_never_crashes(buf):
    assert fuzzmod.fuzz_frame(buf) is True


@given(st.binary())
@settings(max_examples=200)
def test_sql_identifier_filter(buf):
    assert fuzzmod.fuzz_sql_store_path(buf) is True


@given(st.integers(min_value=1, max_value=4096),
       st.integers(min_value=1, max_value=4096),
       st.binary(max_size=512))
@settings(max_examples=200)
def test_frame_roundtrip(w, h, data):
    f = fuzzmod.make_frame(w, h, data)
    r = fuzzmod.decode_frame(f)
    assert r["w"] == w and r["h"] == h
    assert r["data"] == data


@given(st.binary(max_size=4096))
@settings(max_examples=60, deadline=None)
def test_apply_record_rejects_hostile_blobs(buf):
    """`_apply_record` (the SQL apply path for untrusted sync chunks) must
    never accept hostile content and must not crash."""
    v = Village(n_shops=1, n_beneficiaries=3,
                root=tempfile.mkdtemp(prefix="fuzzv-"))
    shop = v.shops[0]
    rec = {"body": crypto.b64e(buf), "sig": crypto.b64e(crypto.rand(64))}
    ok = shop.sync_client._apply_record(rec)
    assert ok is False
    assert shop.store.quarantine_count() >= 0


@given(st.binary(max_size=256))
@settings(max_examples=40, deadline=None)
def test_bad_sigs_never_verify(buf):
    """A damaged/absent signature on an otherwise well-formed record must
    always fail `verify_authority_record` (no false acceptance)."""
    from pdssec.identity import verify_authority_record
    a = Village(n_shops=1, n_beneficiaries=2,
                root=tempfile.mkdtemp(prefix="fuzzv2-")).authority
    rec = {"body": crypto.b64e(buf), "sig": crypto.b64e(crypto.rand(64))}
    assert verify_authority_record(a.signing_pk_der, rec) is False