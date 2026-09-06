# SPDX-License-Identifier: MIT
"""Presentation-attack-detection (PAD) - ISO/IEC 30107-3.

Interface + software emulation + a PAD test rig that produces the ISO 30107-3
reporting quantities:

  * APCER  (Attack Presentation Classification Error Rate): the fraction of
           attack presentations that are classified as bonafide (accepted).
  * BPCER  (Bonafide Presentation Classification Error Rate): the fraction of
           bonafide presentations rejected.
  * Terms  (term1 .. termn): for `conceived` attacks (Level 1 = printed
           photo; Level 2 = video replay, 3D/silicone mask, paper-cutout).

Real hardware may provide a stronger PAD channel (IR/thermal liveness,
structured light, depth); when present the fusion output is
max(live_hw, software_pad) gated at the configured strictness.  The reference
implementation ships the software channel so the whole rig runs offline.
"""

from __future__ import annotations

import random

# ISO/IEC 30107-3 defined attack types used in the rig.
ATTACK_TYPES = ["printed_photo", "video_replay", "silicone_mask",
                "paper_cutout_mask"]


class PADClassifier:
    """Interface: (context) -> liveness prob in [0,1]."""

    def liveness(self, context: dict) -> float:
        raise NotImplementedError


class SoftwarePAD(PADClassifier):
    """Reference software PAD emulation.

    Bonafide frames push the score high; each attack type has a strength band
    (weaker attacks score higher).  In production this is a trained 3D-aware
    network; here the score bands are calibrated so the rig can demonstrate
    APCER/BPCER behaviour end to end.
    """

    BANDS = {
        "bonafide": (0.78, 0.95),
        "printed_photo": (0.10, 0.45),
        "video_replay": (0.12, 0.50),
        "silicone_mask": (0.20, 0.60),
        "paper_cutout_mask": (0.05, 0.30),
    }

    def __init__(self, rng=None):
        self.rng = rng or random

    def liveness(self, context: dict) -> float:
        kind = context.get("kind", "bonafide")
        lo, hi = self.BANDS.get(kind, self.BANDS["printed_photo"])
        return min(1.0, max(0.0, self.rng.uniform(lo, hi)))


class DeterministicPAD(SoftwarePAD):
    """PAD rig helper: force a deterministic per-kind score (band midpoint)."""

    def liveness(self, context: dict) -> float:
        kind = context.get("kind", "bonafide")
        lo, hi = self.BANDS.get(kind, self.BANDS["printed_photo"])
        return (lo + hi) / 2.0


class PADTestRig:
    """ISO/IEC 30107-3 APCER/BPCER rig over an emulated presentation set.

    generate_set(n_bonafide, attacks) → samples
    evaluate(threshold) → APCER (per attack type) + BPCER + overall
    threshold_sweep() → operating curve + recommended threshold
    """

    def __init__(self, classifier: PADClassifier, rng=None):
        self.classifier = classifier
        self.rng = rng or random
        self._set = []

    def generate_set(self, n_bonafide: int = 200,
                     n_per_attack: int = 100,
                     deterministic: bool = False) -> list[dict]:
        """Build a presentation set with ground-truth labels."""
        pad = self.classifier
        self._set = []
        for _ in range(n_bonafide):
            self._set.append({"kind": "bonafide", "label": "bonafide",
                              "score": pad.liveness({"kind": "bonafide"})})
        for kind in ATTACK_TYPES:
            for _ in range(n_per_attack):
                self._set.append({"kind": kind, "label": "attack",
                                  "score": pad.liveness({"kind": kind})})
        return self._set

    def append_sample(self, kind: str, label: str, score: float) -> None:
        self._set.append({"kind": kind, "label": label, "score": score})

    def evaluate(self, threshold: float) -> dict:
        """ACCEPT if liveness >= threshold.

        APCER_k = P(attack_k classified bonafide)
        BPCER   = P(bonafide classified attack)
        """
        bonafide = [s for s in self._set if s["label"] == "bonafide"]
        apcer: dict[str, float] = {}
        for kind in ATTACK_TYPES:
            attacks = [s for s in self._set if s["kind"] == kind]
            if attacks:
                rejected = sum(1 for s in attacks if s["score"] >= threshold)
                apcer[kind] = rejected / len(attacks)
        bpcer = sum(1 for s in bonafide if s["score"] < threshold) / len(bonafide) \
            if bonafide else 0.0
        attacks_all = [s for s in self._set if s["label"] == "attack"]
        overall_apcer = sum(
            1 for s in attacks_all if s["score"] >= threshold
        ) / len(attacks_all) if attacks_all else 0.0
        target = {"level": None}  # placeholder for target-level checks
        return {"threshold": threshold, "APCER": apcer, "overall_APCER":
                overall_apcer, "BPCER": bpcer, "n_bonafide": len(bonafide),
                "target": target}

    def threshold_for(self, max_apcer: float = 0.01,
                      max_bpcer: float = 0.05) -> dict:
        """Pick the loosest threshold meeting APCER<=max_apcer and
        BPCER<=max_bpcer (fail-closed direction for PAD: APCER first)."""
        best = None
        for t in [round(x / 1000, 3) for x in range(0, 1001)]:
            r = self.evaluate(t)
            if r["overall_APCER"] <= max_apcer and r["BPCER"] <= max_bpcer:
                if best is None or t > best:
                    best = t
        return self.evaluate(best) if best is not None else \
            {"threshold": None, "reason": "no threshold meets both targets"}

    def sweep(self, step: float = 0.05) -> list[dict]:
        out = []
        t = 0.0
        while t <= 1.0 + 1e-9:
            out.append(self.evaluate(round(t, 3)))
            t += step
        return out

    def report(self, threshold: float) -> str:
        r = self.evaluate(threshold)
        lines = ["ISO/IEC 30107-3 PAD report",
                 f"  threshold (liveness >=): {r['threshold']:.3f}",
                 f"  BPCER (bonafide rejected): {r['BPCER']*100:.2f}%",
                 f"  overall APCER: {r['overall_APCER']*100:.2f}%"]
        for kind, a in r["APCER"].items():
            lines.append(f"  APCER[{kind}]: {a*100:.2f}%")
        return "\n".join(lines)