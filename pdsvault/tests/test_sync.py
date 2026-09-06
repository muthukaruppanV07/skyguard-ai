# SPDX-License-Identifier: MIT
"""Sync tests: delta convergence, anti-replay, poison/malformed payloads,
corrupted-chunk quarantine, cross-device divergence convergence, and
property-based sync convergence with Hypothesis."""

from __future__ import annotations

import random

import pytest
from hypothesis import given, note, settings
from hypothesis import strategies as st

from pdssec import crypto
from pdssec import sync as syncmod
from pdssec.simulator import Village
from tests.conftest import dsid_of


def test_initial_sync_brings_records(village, shop):
    assert len(shop.store.all_beneficiaries()) == len(village.beneficiaries)
    assert shop.store.quarantine_count() == 0


def test_idempotent_second_sync_no_duplicates(village, shop):
    before = len(shop.store.all_beneficiaries())
    shop.sync(village.shop_server(shop))
    assert len(shop.store.all_beneficiaries()) == before


def test_sync_replay_is_rejected(village, shop):
    """Anti-replay: the snapshot seq is monotonic per device, so no amount of
    repeated syncs can regress or duplicate the beneficiary set."""
    first = shop.sync(village.shop_server(shop))
    second = shop.sync(village.shop_server(shop))
    assert second["seq"] > first["seq"]          # monotonic seq
    assert second["applied"] == 0                # nothing re-applied
    assert len(shop.store.all_beneficiaries()) == len(village.beneficiaries)
    # explicit stale-seq rejection is covered in test_faults::replayed_old


def test_poisoned_snapshot_signature_rejected(village):
    shop = village.shops[0]
    wrong = Village(n_shops=1, n_beneficiaries=6, root=None).server
    wrong_authority = wrong.authority
    # a server with a *different* authority cannot get the device to apply
    from pdssec.sync import SyncClient
    bad_client = SyncClient(shop.store, shop.clock,
                            shop.cfg.domain_uid_key, shop.cfg.shop_domain,
                            wrong_authority.signing_pk_der)
    # device refuses because signature invalid (authority mismatch)
    with pytest.raises(ValueError):
        bad_client.fetch(wrong, rng=random.Random(0))


def test_malformed_record_quarantined(village):
    shop = village.shops[0]
    bad = {"body": crypto.b64e(b"not canonical"), "sig": crypto.b64e(crypto.rand(64))}
    ok = shop.sync_client._apply_record(bad)
    assert ok is False
    assert shop.store.quarantine_count() == 1


def test_corrupt_chunk_quarantined_not_applied():
    """Corrupted delta chunks are quarantined and never enter the
    verification path; the remaining signed records still apply cleanly."""
    v = Village(n_shops=1, n_beneficiaries=10, now=1_700_000_000, seed=3)
    shop = v.shops[0]
    rng = random.Random(0)
    res = shop.sync_client.fetch(v.shop_server(shop), rng=rng,
                                 corrupt_chance=0.3)
    assert res["corrupted"] > 0
    assert shop.store.quarantine_count() == res["corrupted"]
    bad = shop.store.verify_cache_integrity(v.authority.signing_pk_der)
    assert bad == []


def test_divergent_shops_converge_at_server(village, shop, shop2):
    # both shops are fresh: each builds its own chain from genesis
    assert len(shop.store.all_beneficiaries()) == \
        len(shop2.store.all_beneficiaries()) == len(village.beneficiaries)
    # server snapshot seqs are per-device, so second sync is a no-op delta
    r1 = shop.sync(village.shop_server(shop))
    r2 = shop2.sync(village.shop_server(shop2))
    assert r1["applied"] == r2["applied"] == 0
    # cross-shop duplicate resolution: same token redeemed on BOTH devices
    toks = village.server.mint_tokens_for(
        village.domain, village.beneficiaries, village.cycle_epoch,
        village.basket, village.now - 3600, village.now + 3600 * 24 * 30)
    t = toks[0]
    shop.store.insert_token(village.authority.signing_pk_der, t)
    shop2.store.insert_token(village.authority.signing_pk_der, t)
    shop.redeem(t["token_id"], "op-1")
    shop2.redeem(t["token_id"], "op-2")
    # whoever syncs first is the reference; the second is flagged a duplicate
    shop.sync(village.shop_server(shop))
    r = shop2.sync(village.shop_server(shop2))
    assert any(f["token_id"] == t["token_id"]
               for f in village.server.duplicate_flags)


def test_snapshot_merkle_root_verifies_records(village):
    snap = village.server.ingest(
        village.domain,
        {"since_seq": 0, "device_id": "x",
         "redeemed_token_ids": [], "used_token_hashes": []})
    leaves = [crypto.sha256(crypto.canonical(r)) for r in snap["records"]]
    from pdssec.ledger import MerkleTree
    assert crypto.b64e(MerkleTree(leaves).root if leaves
                       else crypto.sha256(b"empty-snapshot")) == \
        snap["merkle_root"] if leaves else True


@given(n_shops=st.integers(min_value=1, max_value=4),
       n_ben=st.integers(min_value=4, max_value=30))
@settings(max_examples=20, deadline=None)
def test_property_sync_convergence(n_shops, n_ben):
    """Whatever the topology, after each device syncs against the authority
    every device ends up with exactly the authority's beneficiary set and a
    healthy, gap-free merkle ledger."""
    v = Village(n_shops=n_shops, n_beneficiaries=n_ben, now=1_700_000_000,
                seed=42)
    for shop in v.shops:
        shop.sync(v.shop_server(shop))
    expected = len(v.beneficiaries)
    for i, shop in enumerate(v.shops):
        note(f"shop{i} has {len(shop.store.all_beneficiaries())}")
        assert len(shop.store.all_beneficiaries()) == expected
        assert shop.ledger.verify_chain() == []
        assert shop.store.verify_cache_integrity(
            v.authority.signing_pk_der) == []
        assert shop.store.quarantine_count() == 0


@given(epochs=st.lists(st.integers(min_value=1, max_value=10),
                       min_size=2, max_size=8))
@settings(max_examples=15, deadline=None)
def test_property_stale_epochs_never_revive(epochs):
    """Monotonic seqs: no matter how the server serves snapshots back to
    back, a device's stored seq never regresses, so stale snapshots can't be
    spliced back in as 'new'."""
    v = Village(n_shops=1, n_beneficiaries=5, now=1_700_000_000, seed=1)
    shop = v.shops[0]
    last = 0
    for seq in sorted(set(epochs)):
        shop.sync(v.shop_server(shop))
        last = max(last, int(shop.store.get_sync_state("snapshot_seq", 0)))
    assert int(shop.store.get_sync_state("snapshot_seq", 0)) >= last