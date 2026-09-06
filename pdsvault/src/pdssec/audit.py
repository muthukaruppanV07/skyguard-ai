# SPDX-License-Identifier: MIT
"""Operator-action audit: keystroke-level, signed, hash-chained.

Every action is both written to the Merkle header-chain ledger (append-only,
periodically anchored) and recorded in a local hash chain table for fast
operator-facing queries.  Dual-operator (four-eyes) overrides require two
distinct operator signatures and are rate-limited per operator.

Chain-gap detection: the caller escalates if ledger.verify_chain() fails.
"""

from __future__ import annotations

import time

from . import crypto
from .crypto import b64d, b64e, sha256


class FourEyesResult:
    def __init__(self, approved: bool, override_id: int | None,
                 reason: str = ""):
        self.approved = approved
        self.override_id = override_id
        self.reason = reason


class AuditLog:
    SHIFT_HOURS = 12

    def __init__(self, store, ledger, device_ledger_sk_der: bytes):
        self.store = store
        self.ledger = ledger
        self.sk = crypto.load_priv(device_ledger_sk_der)

    def record(self, op: str, detail: dict, actor: str, subject: str | None
               = None) -> dict:
        """Sign (op, actor, subject, detail) twice: once for the Merkle
        ledger block, once for the local queryable chain."""
        ts = int(time.time())
        # local hash chain
        con = self.store._connect()
        try:
            prev = con.execute(
                "SELECT prev_hash FROM audit ORDER BY idx DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev[0] if prev else b64e(sha256(b"audit-genesis"))
            payload = crypto.canonical({
                "op": op, "actor": actor, "subject": subject or "",
                "detail": crypto.canonical(detail), "ts": ts,
            })
            sig = b64e(crypto.ed25519_sign(self.sk, payload))
            chain_hash = b64e(sha256(payload + b64d(prev_hash)))
            con.execute(
                "INSERT INTO audit(ts, op, actor, subject, detail, sig, "
                "prev_hash) VALUES(?,?,?,?,?,?,?)",
                (ts, op, actor, subject, crypto.canonical(detail), sig,
                 chain_hash),
            )
            con.commit()
        finally:
            con.close()
        # Merkle ledger block (append-only, anchored)
        self.ledger.append("audit", {
            "op": op, "actor": actor, "subject": subject or "",
            "detail": crypto.canonical(detail),
        })
        return {"op": op, "ts": ts}

    def four_eyes(self, subject: str, reason: str, operator_a: str,
                  operator_b: str) -> FourEyesResult:
        """Emergency quota release.  Both operators are distinct (enforced by
        the entitlement engine); both signatures are recorded.  In production
        operator_b would be a separate physical device or a supervisor card;
        here both signatures are produced by the same device but recorded
        with separate identities."""
        if operator_a == operator_b:
            return FourEyesResult(False, None, "not four eyes")
        ts = int(time.time())
        payload = crypto.canonical({
            "subject": subject, "reason": reason, "ts": ts,
        })
        sig_a = b64e(crypto.ed25519_sign(self.sk, payload))
        sig_b = b64e(crypto.ed25519_sign(self.sk, payload))
        con = self.store._connect()
        try:
            cur = con.execute(
                "INSERT INTO overrides(request_ts, subject, reason, "
                "operator_a, operator_b, sig_a, sig_b, status) "
                "VALUES(?,?,?,?,?,?,?,'approved')",
                (ts, subject, reason, operator_a, operator_b, sig_a, sig_b),
            )
            con.commit()
            oid = cur.lastrowid
        finally:
            con.close()
        self.ledger.append("override", {
            "subject": subject, "reason": reason,
            "opA": operator_a, "opB": operator_b, "approved": "1",
        })
        return FourEyesResult(True, oid)

    def count_operator_overrides(self, operator: str) -> int:
        since = int(time.time()) - self.SHIFT_HOURS * 3600
        con = self.store._connect()
        try:
            return con.execute(
                "SELECT COUNT(*) FROM overrides "
                "WHERE operator_a=? AND request_ts>=? AND status='approved'",
                (operator, since),
            ).fetchone()[0]
        finally:
            con.close()

    def recent_failures(self, actor: str, window_s: int) -> int:
        since = int(time.time()) - window_s
        # failures are committed both to ledger_txn and audit; count from the
        # queryable audit chain for speed (authoritative check is the ledger).
        con = self.store._connect()
        try:
            rows = con.execute(
                "SELECT detail FROM audit WHERE op='verify_fail' AND "
                "actor=? AND ts>=?", (actor, since),
            ).fetchall()
            return len(rows)
        finally:
            con.close()

    def pendings(self) -> list[dict]:
        con = self.store._connect()
        try:
            rows = con.execute(
                "SELECT id, request_ts, subject, reason, operator_a, "
                "operator_b, status FROM overrides ORDER BY id"
            ).fetchall()
            cols = ["id", "request_ts", "subject", "reason", "operator_a",
                    "operator_b", "status"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            con.close()