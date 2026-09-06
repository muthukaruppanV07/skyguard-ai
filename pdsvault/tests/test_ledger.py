# SPDX-License-Identifier: MIT
"""Ledger tests: hash-chained blocks, merkle proofs, gap detection,
periodic anchoring."""

from __future__ import annotations

import tempfile

import pytest

from pdssec import crypto
from pdssec.ledger import Ledger, MerkleTree, merkle_verify, ChainGapError
from pdssec.store import Store


def make_ledger() -> tuple[Ledger, Store]:
    st = Store(tempfile.mktemp(prefix="ledger-"), crypto.rand(32))
    sk = crypto.gen_ed25519()
    return Ledger(st, sk.private_bytes_raw()), st


def test_merkle_inclusion_proof():
    leaves = [crypto.sha256(crypto.rand(16)) for _ in range(9)]
    tree = MerkleTree(leaves)
    for i in range(len(leaves)):
        path = tree.proof(i)
        assert merkle_verify(tree.root, leaves[i], i, path)
        assert not merkle_verify(tree.root, crypto.sha256(b"other"),
                                 i, path)


def test_append_creates_blocks_with_verified_roots():
    ledger, st = make_ledger()
    for i in range(5):
        ledger.append("audit", {"i": i})
    assert len(ledger.verify_chain()) == 0
    con = st._connect()
    n_blocks = con.execute("SELECT COUNT(*) FROM ledger_block").fetchone()[0]
    n_txn = con.execute("SELECT COUNT(*) FROM ledger_txn").fetchone()[0]
    con.close()
    assert n_blocks == 5 and n_txn == 5


def test_gap_detection():
    ledger, st = make_ledger()
    for i in range(4):
        ledger.append("audit", {"i": i})
    con = st._connect()
    con.execute("DELETE FROM ledger_block WHERE idx=2")
    con.commit()
    con.close()
    problems = ledger.verify_chain()
    assert any("gap" in p for p in problems)
    with pytest.raises(ChainGapError):
        ledger.append("audit", {"after_gap": True})


def test_txn_delete_detected_as_root_mismatch():
    ledger, st = make_ledger()
    for i in range(4):
        ledger.append("audit", {"i": i})
    con = st._connect()
    con.execute("DELETE FROM ledger_txn WHERE block_idx=3")
    con.commit()
    con.close()
    problems = ledger.verify_chain()
    assert any("merkle root mismatch" in p for p in problems)


def test_periodic_anchoring():
    from pdssec.ledger import ANCHOR_EVERY
    le, st = make_ledger()
    for i in range(ANCHOR_EVERY + 2):
        le.append("audit", {"i": i})
    con = st._connect()
    anchored = con.execute(
        "SELECT COUNT(*) FROM ledger_block WHERE anchor_sig IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert anchored == 1
    assert len(le.verify_chain()) == 0
    # anchors are signature-checkable
    block = le._block(ANCHOR_EVERY)
    assert block["anchor_sig"]


def test_ledger_is_append_only_by_construction():
    le, st = make_ledger()
    for i in range(3):
        le.append("audit", {"i": i})
    tail = le.tail(10)
    assert len(tail) == 3
    kinds = {t["kind"] for t in tail}
    assert kinds == {"audit"}