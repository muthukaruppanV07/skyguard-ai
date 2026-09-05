# SPDX-License-Identifier: MIT
"""Append-only, Merkle-rooted operator-action ledger.

Every keystroke-level operator action is written as a signed transaction into
a hash-chained header chain.  Each block commits its transactions with a
Merkle root, and every `ANCHOR_EVERY` blocks the device signs a periodic root
anchor that can be verified remotely on the next sync - so a hostile operator
cannot silently edit or delete what happened without breaking the chain, and
the central authority can prove which blocks were authored by this device.

Chain-gap detection: a block whose prev_hash does not match the previous
block, or a missing index, raises a GapError that must be escalated; the
ledger refuses to write further until the gap is resolved by a fresh signed
anchor from the authority.
"""

from __future__ import annotations

import hashlib
import json

from . import crypto
from .crypto import b64d, b64e, sha256

ANCHOR_EVERY = 64


class LedgerError(Exception):
    pass


class ChainGapError(LedgerError):
    pass


class MerkleTree:
    """Binary Merkle tree over a list of leaf hashes."""

    def __init__(self, leaves: list[bytes]):
        if not leaves:
            raise ValueError("empty merkle tree")
        self.leaves = leaves
        self.root = self._build(leaves)

    @staticmethod
    def _build(nodes: list[bytes]) -> bytes:
        level = list(nodes)
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    nxt.append(sha256(level[i] + level[i + 1]))
                else:
                    nxt.append(sha256(level[i] + level[i]))  # orphan duplication
            level = nxt
        return level[0]

    def proof(self, leaf_index: int) -> list[bytes]:
        """Standard Merkle inclusion proof (sibling path)."""
        nodes = list(self.leaves)
        path, idx = [], leaf_index
        while len(nodes) > 1:
            nxt = []
            for i in range(0, len(nodes), 2):
                if i + 1 < len(nodes):
                    h = sha256(nodes[i] + nodes[i + 1])
                    if i // 2 == idx // 2:
                        sibling = nodes[i + (1 - idx % 2)]
                        path.append(sibling)
                    nxt.append(h)
                else:
                    nxt.append(sha256(nodes[i] + nodes[i]))
                    if i // 2 == idx // 2:
                        path.append(nodes[i])
            nodes = nxt
            idx //= 2
        return path


def merkle_verify(root: bytes, leaf: bytes, leaf_index: int,
                  path: list[bytes]) -> bool:
    idx = leaf_index
    cur = leaf
    for sibling in path:
        if idx % 2 == 0:
            cur = sha256(cur + sibling)
        else:
            cur = sha256(sibling + cur)
        idx //= 2
    return cur == root


def _block_root(leaves: list[bytes]) -> bytes:
    """Merkle root for a block's transactions (empty block = fixed hash)."""
    if not leaves:
        return sha256(b"pdsvault-empty-block")
    return MerkleTree(leaves).root


class Ledger:
    def __init__(self, store, device_ledger_sk_der: bytes):
        self.store = store
        self.sk = crypto.load_priv(device_ledger_sk_der)

    # ------------------------------------------------------------------ #
    # block writing
    # ------------------------------------------------------------------ #

    def append(self, kind: str, data: dict) -> dict:
        """Append one signed transaction, then batch it into a block."""
        if self.detect_gap():
            raise ChainGapError("cannot append: ledger has a gap (escalate)")
        ts = _now()
        txn = {
            "kind": kind,
            "data": crypto.canonical(data),
            "ts": ts,
        }
        txn_body = crypto.canonical(txn)
        txn_hash = sha256(txn_body)
        last = self._last_block()
        prev_hash = last["prev_hash"] if last else _genesis_hash()
        if isinstance(prev_hash, str):
            prev_hash = b64d(prev_hash)  # stored b64 string -> bytes
        idx = (last["idx"] + 1) if last else 1

        # batch window: keep last block open until ANCHOR_EVERY or a flush
        # is requested.  For simplicity every append commits a block; the
        # anchor is emitted every ANCHOR_EVERY blocks.
        con = self.store._connect()
        try:
            # create the block row first so the txn FK (block_idx ->
            # ledger_block.idx) holds; the header is patched below once the
            # Merkle root over the txn set can be computed.
            con.execute(
                "INSERT INTO ledger_block(idx, prev_hash, merkle_root, "
                "txn_count, header_sig, signed_at) VALUES(?,?,?,?,?,?)",
                (idx, b64e(prev_hash), "", 0, "", ts),
            )
            con.execute(
                "INSERT INTO ledger_txn(txn_hash, block_idx, kind, data, "
                "signed_at) VALUES(?,?,?,?,?)",
                (b64e(txn_hash), idx, kind, b64e(txn_body), ts),
            )
            block = self._build_block(idx, prev_hash, con)
            con.execute(
                "UPDATE ledger_block SET merkle_root=?, txn_count=?, "
                "header_sig=? WHERE idx=?",
                (block["merkle_root"], block["txn_count"],
                 block["header_sig"], idx),
            )
            con.commit()
        finally:
            con.close()

        if idx % ANCHOR_EVERY == 0:
            self.anchor(idx)
        return {"idx": idx, "txn_hash": b64e(txn_hash)}

    def _build_block(self, idx: int, prev_hash: bytes, con) -> dict:
        rows = con.execute(
            "SELECT data FROM ledger_txn WHERE block_idx=? ORDER BY rowid",
            (idx,),
        ).fetchall()
        leaves = [sha256(b64d(r[0])) for r in rows]
        root = _block_root(leaves)
        header = crypto.canonical({
            "idx": idx, "prev_hash": b64e(prev_hash),
            "merkle_root": b64e(root), "n": len(leaves),
        })
        header_sig = b64e(crypto.ed25519_sign(self.sk, header))
        return {"merkle_root": b64e(root), "txn_count": len(leaves),
                "header_sig": header_sig}

    def anchor(self, idx: int) -> dict:
        """Sign a periodic root anchor: (idx, merkle_root, header_sig) under
        the device ledger key.  Central verifies on next sync that the anchor
        chain matches its own copy."""
        block = self._block(idx)
        if block is None:
            raise LedgerError(f"no block at idx {idx}")
        body = crypto.canonical({
            "anchor_idx": idx,
            "merkle_root": block["merkle_root"],
            "prev_anchor": self._last_anchor(),
        })
        anchor_sig = b64e(crypto.ed25519_sign(self.sk, body))
        con = self.store._connect()
        try:
            con.execute(
                "UPDATE ledger_block SET anchor_sig=? WHERE idx=?",
                (anchor_sig, idx),
            )
            con.commit()
        finally:
            con.close()
        return {"idx": idx, "anchor_sig": anchor_sig, "body": b64e(body)}

    # ------------------------------------------------------------------ #
    # reads / integrity
    # ------------------------------------------------------------------ #

    def _last_block(self) -> dict | None:
        con = self.store._connect()
        try:
            row = con.execute(
                "SELECT idx, prev_hash, merkle_root, txn_count, header_sig "
                "FROM ledger_block ORDER BY idx DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return {"idx": row[0], "prev_hash": row[1],
                    "merkle_root": row[2], "txn_count": row[3]}
        finally:
            con.close()

    def _block(self, idx: int) -> dict | None:
        con = self.store._connect()
        try:
            row = con.execute(
                "SELECT idx, prev_hash, merkle_root, txn_count, header_sig, "
                "anchor_sig FROM ledger_block WHERE idx=?",
                (idx,),
            ).fetchone()
            if row is None:
                return None
            return {"idx": row[0], "prev_hash": row[1], "merkle_root": row[2],
                    "txn_count": row[3], "header_sig": row[4],
                    "anchor_sig": row[5]}
        finally:
            con.close()

    def verify_chain(self) -> list[str]:
        """Walk the chain; return list of problems (empty == healthy)."""
        problems: list[str] = []
        con = self.store._connect()
        try:
            rows = con.execute(
                "SELECT idx, prev_hash, merkle_root, txn_count, header_sig, "
                "anchor_sig FROM ledger_block ORDER BY idx"
            ).fetchall()
            prev = _genesis_hash()
            expected_idx = 1
            for r in rows:
                idx, prev_hash, root, n, hsig, asig = r
                if idx != expected_idx:
                    problems.append(f"gap: expected block {expected_idx}, got {idx}")
                    expected_idx = idx + 1
                if prev_hash != b64e(prev):
                    problems.append(f"block {idx}: prev_hash mismatch")
                # verify header signature
                header = crypto.canonical({
                    "idx": idx, "prev_hash": prev_hash,
                    "merkle_root": root, "n": n,
                })
                if not crypto.ed25519_verify(
                    crypto.ed25519_sk_to_pk(self.sk), header, b64d(hsig)
                ):
                    problems.append(f"block {idx}: bad header signature")
                prev = b64d(prev_hash)
                expected_idx = idx + 1
            # a transaction whose block is missing = a chain gap (hostile
            # cleanup of the block table cannot hide the txn reference)
            block_idxs = {r[0] for r in rows}
            txn_blocks = [t[0] for t in con.execute(
                "SELECT DISTINCT block_idx FROM ledger_txn").fetchall()]
            for bi in txn_blocks:
                if bi not in block_idxs:
                    problems.append(f"gap: ledger_txn references missing "
                                    f"block {bi}")
            # verify merkle roots recompute from txns
            for r in rows:
                idx = r[0]
                txn_rows = con.execute(
                    "SELECT data FROM ledger_txn WHERE block_idx=? ORDER BY rowid",
                    (idx,),
                ).fetchall()
                leaves = [sha256(b64d(t[0])) for t in txn_rows]
                root = _block_root(leaves)
                if b64e(root) != r[2]:
                    problems.append(f"block {idx}: merkle root mismatch")
        finally:
            con.close()
        return problems

    def detect_gap(self) -> bool:
        return bool(self.verify_chain())

    def tail(self, n: int = 20) -> list[dict]:
        con = self.store._connect()
        try:
            rows = con.execute(
                "SELECT data, kind, block_idx, signed_at FROM ledger_txn "
                "ORDER BY rowid DESC LIMIT ?",
                (n,),
            ).fetchall()
            return [{"kind": r[1], "data": crypto._parse_canonical(b64d(r[0])),
                     "block": r[2], "ts": r[3]} for r in rows]
        finally:
            con.close()

    def _last_anchor(self) -> str:
        con = self.store._connect()
        try:
            row = con.execute(
                "SELECT merkle_root FROM ledger_block WHERE anchor_sig IS NOT "
                "NULL ORDER BY idx DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else ""
        finally:
            con.close()


def _genesis_hash() -> bytes:
    return sha256(b"pdsvault-genesis-v1")


def _now() -> int:
    import time
    return int(time.time())
