# SPDX-License-Identifier: MIT
"""PAD rig tests: ISO/IEC 30107-3 APCER/BPCER reporting, threshold
selection, and attack-type discrimination."""

from __future__ import annotations

import pytest

from pdssec.pad import (ATTACK_TYPES, DeterministicPAD, PADTestRig,
                        SoftwarePAD)


def test_deterministic_rig_reports_apcer_bpcer():
    rig = PADTestRig(DeterministicPAD())
    rig.generate_set(n_bonafide=200, n_per_attack=100)
    r = rig.evaluate(0.5)
    for kind in ATTACK_TYPES:
        assert kind in r["APCER"]
    assert 0 <= r["BPCER"] <= 1
    assert 0 <= r["overall_APCER"] <= 1


def test_threshold_selection_meets_targets():
    rig = PADTestRig(DeterministicPAD())
    rig.generate_set(n_bonafide=200, n_per_attack=100)
    r = rig.threshold_for(max_apcer=0.01, max_bpcer=0.05)
    assert r["overall_APCER"] <= 0.01
    assert r["BPCER"] <= 0.05


def test_attack_types_are_distinct():
    # silicone mask is the strongest attack; paper cutout the weakest
    pad = DeterministicPAD()
    scores = {k: pad.liveness({"kind": k}) for k in ATTACK_TYPES}
    bonafide = pad.liveness({"kind": "bonafide"})
    assert scores["paper_cutout_mask"] < scores["silicone_mask"]
    assert bonafide > max(scores.values())


def test_attack_or_bonafide_labels_present():
    rig = PADTestRig(SoftwarePAD())
    s = rig.generate_set(n_bonafide=50, n_per_attack=10)
    assert all(x["label"] in ("bonafide", "attack") for x in s)
    assert any(x["label"] == "bonafide" for x in s)


def test_apcer_per_attack_type_ranked():
    rig = PADTestRig(DeterministicPAD())
    rig.generate_set(n_bonafide=100, n_per_attack=50)
    r = rig.evaluate(0.45)
    # paper cutouts are far below threshold -> ~0 APCER
    assert r["APCER"]["paper_cutout_mask"] < 0.1
    # silicone masks can sneak closer to the decision boundary
    assert r["APCER"]["silicone_mask"] >= r["APCER"]["paper_cutout_mask"]


def test_sweep_monotonic_bpcer():
    rig = PADTestRig(DeterministicPAD())
    rig.generate_set(n_bonafide=100, n_per_attack=50)
    rows = rig.sweep(step=0.25)
    bpcers = [r["BPCER"] for r in rows if r["threshold"] is not None]
    assert bpcers == sorted(bpcers)