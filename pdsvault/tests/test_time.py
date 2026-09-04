# SPDX-License-Identifier: MIT
"""Secure-clock tests: anchor installation, backward-jump detection,
forward-jump suspicion, no-anchor fail-closed, monotonic source."""

from __future__ import annotations

import pytest

from pdssec import crypto, timekeeper
from pdssec.auth import build_clock_anchor
from pdssec.identity import Authority


@pytest.fixture
def caf():
    a = Authority.generate()
    return a


def test_anchor_installed_and_time_advances(caf):
    c = timekeeper.SecureClock()
    anchor = build_clock_anchor(caf, 1_000_000, "shopA")
    c.set_anchor(anchor, caf.signing_pk_der)
    assert c.now() >= 1_000_000


def test_no_anchor_fails_closed(caf):
    c = timekeeper.SecureClock()
    with pytest.raises(timekeeper.ClockTamperError):
        c.now()


def test_backward_anchor_rejected(caf):
    c = timekeeper.SecureClock()
    a1 = build_clock_anchor(caf, 3_000_000, "shopA")
    c.set_anchor(a1, caf.signing_pk_der)
    a0 = build_clock_anchor(caf, 1_000_000, "shopA")
    with pytest.raises(timekeeper.ClockTamperError):
        c.set_anchor(a0, caf.signing_pk_der)


def test_forged_anchor_signature_rejected(caf):
    c = timekeeper.SecureClock()
    other = Authority.generate()
    anchor = build_clock_anchor(other, 1_000_000, "shopA")
    with pytest.raises(timekeeper.ClockTamperError):
        c.set_anchor(anchor, caf.signing_pk_der)


def test_backward_wall_clock_detected(caf):
    c = timekeeper.SecureClock()
    a = build_clock_anchor(caf, 5_000_000, "shopA")
    c.set_anchor(a, caf.signing_pk_der)
    c.now_verified(5_000_000)
    with pytest.raises(timekeeper.ClockTamperError):
        c.now_verified(4_000_000)  # rewound


def test_monotonic_source_never_goes_back():
    m = timekeeper._MonotonicSource()
    a = m.now()
    b = m.now()
    assert b >= a


def test_safe_has_anchor():
    c = timekeeper.SecureClock()
    assert not c.safe_has_anchor()