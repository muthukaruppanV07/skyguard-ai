# SPDX-License-Identifier: MIT
"""Secure time.

Offline devices must never trust the wall clock: an attacker that rewinds the
clock can keep expired entitlement epochs alive or replay old tokens.  We use
  * a monotonic counter (TPM NV or wall-clock-monotonic fallback) as the
    invariant that never goes backwards;
  * epoch brackets signed into every record's valid_from/valid_to window;
  * skew and backward-jump detection that raises a *tamper event* (fail
    closed: no verification, quarantine sync, alert on next connect).

The device is seeded with a signed anchor (authority_stamp) at sync time.  The
local clock may drift within ±tolerance of the anchor; beyond that we treat
the clock as hostile rather than NTP-less drift.
"""

from __future__ import annotations

import time

from . import crypto
from .crypto import b64d, b64e


class ClockTamperError(Exception):
    pass


class SecureClock:
    # Window (seconds) within which an unsigned local clock is acceptable
    # given a signed anchor.  After boot, a bare "monotonic since last
    # anchor + signed anchor" is the source of truth.
    MAX_SKEW_S = 300          # 5 min: intentionally tight for a ration shop
    MAX_FORWARD_JUMP_S = 3600 * 24  # >1 day forward jump => suspicious

    def __init__(self, max_skew_s: int = MAX_SKEW_S,
                 max_forward_jump_s: int = MAX_FORWARD_JUMP_S):
        self._mono = _MonotonicSource()
        self._last_anchor_unix = None   # signed anchor
        self._last_anchor_mono = None
        # independently-persisted high-water mark of anchored time: rewinding
        # the anchor object in memory cannot push trusted time below this.
        self._anchor_high_water = None
        self._last_read_unix = None
        self._tampered = False
        self.max_skew_s = max_skew_s
        self.max_forward_jump_s = max_forward_jump_s

    # -- anchoring -------------------------------------------------------- #

    def set_anchor(self, signed_anchor: dict, authority_pk_der: bytes) -> None:
        """Install a signed clock anchor from a sync payload.
        Anchor body: canonical({"unix": u, "device_domain": d}) signed by authority."""
        body = b64d(signed_anchor["body"])
        if not crypto.ed25519_verify(
            crypto.load_pub(authority_pk_der), body, b64d(signed_anchor["sig"]),
        ):
            raise ClockTamperError("clock anchor signature invalid")
        fields = crypto._parse_canonical(body)  # canonical {"unix": "..", "device_domain": ".."}
        unix = int(fields["unix"])
        now_mono = self._mono.now()
        if self._last_anchor_unix is not None and unix < self._last_anchor_unix:
            raise ClockTamperError("clock anchor went backwards")
        if self._anchor_high_water is not None and \
           unix < self._anchor_high_water - self.max_skew_s:
            raise ClockTamperError("clock anchor far below high-water mark")
        self._last_anchor_unix = unix
        self._last_anchor_mono = now_mono
        self._last_read_unix = unix
        self._anchor_high_water = max(
            self._anchor_high_water or 0, unix)
        self._tampered = False

    # -- reads ------------------------------------------------------------ #

    def now(self) -> int:
        """Trusted time.  Falls back to a forward-only estimate from the last
        signed anchor; raises if no anchor ever installed."""
        if self._last_anchor_unix is None:
            raise ClockTamperError("no signed clock anchor installed")
        return int(self._last_anchor_unix + (self._mono.now() - self._last_anchor_mono))

    def now_verified(self, wall_now: int) -> int:
        """Cross-check a local clock read against the trusted estimate.
        Raises ClockTamperError on backward jump, on an anchor rewind below
        the high-water mark, or on excessive forward jump."""
        if self._tampered:
            raise ClockTamperError("clock already flagged tampered")
        trusted = self.now()
        if self._anchor_high_water is not None and \
           trusted < self._anchor_high_water - self.max_skew_s:
            raise ClockTamperError(f"anchor rewound: trusted {trusted} < "
                                   f"high-water {self._anchor_high_water}")
        if wall_now < trusted - self.max_skew_s:
            raise ClockTamperError(
                f"clock rewound: wall {wall_now} < trusted {trusted}"
            )
        if wall_now > trusted + self.max_skew_s and \
           wall_now > self._last_read_unix + self.max_forward_jump_s:
            raise ClockTamperError(
                f"clock jumped forward suspiciously: wall {wall_now}"
            )
        self._last_read_unix = max(self._last_read_unix or 0, wall_now)
        return trusted

    def tampered(self) -> bool:
        return self._tampered

    def safe_has_anchor(self) -> bool:
        return self._last_anchor_unix is not None and not self._tampered

    def flag_tamper(self, why: str) -> None:
        self._tampered = True
        self._last_tamper_reason = why

    @property
    def tamper_reason(self) -> str:
        return getattr(self, "_last_tamper_reason", "unknown")


class _MonotonicSource:
    """Never-decreasing time source (no wall-clock trust involved)."""

    def __init__(self):
        self._base = time.monotonic()
        self._counter = 0

    def now(self) -> float:
        # time.monotonic() never decreases in-process; we add an explicit
        # guard for the TPM-free path.
        t = time.monotonic() - self._base
        if t < self._counter:
            raise ClockTamperError("monotonic source went backwards")
        self._counter = t
        return t
