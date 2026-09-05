# SPDX-License-Identifier: MIT
"""Face matching pipeline (plug-in interface).

Production flow on the target SoC (RK3588/RK3566):
  camera → face det (SCRFD) → alignment → embed (quant) → cosine vs enrolled
  templates → threshold decision.

This reference module provides pure-Python vector math (no heavy deps) plus a
documented INT8-quantization policy:
  * ArcFace/InsightFace 512-d embedding: float32 ~= 2 KB/template.
  * INT8 quantised (per-row scale): 512 B/template; accuracy delta typically
    <0.3% TAR loss at same FAR (measure on the target set, see docs).
  * Matching is cosine distance; threshold tunes the operating point.

The `SimMatcher` exists for end-to-end prototyping / fault injection: it draws
scores from genuine/impostor score distributions so the whole pipeline can be
run without a trained model and the documented FAR/FRR behaviour can be
asserted.
"""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        raise ValueError("template dimension mismatch")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom == 0.0:
        return 0.0
    return dot / denom


def cosine_dist(a: list[float], b: list[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


class Matcher:
    """Interface: enroll templates, verify a probe against a template set."""

    DEF_FAR = 1e-4  # target FAR for high-value claims (see docs)

    def __init__(self, threshold: float):
        self.threshold = threshold
        self.enrolled: dict[str, list[float]] = {}

    def enroll(self, dsid: str, template: list[float]) -> None:
        self.enrolled[dsid] = template

    def verify(self, probe: list[float]) -> tuple[str, float]:
        """Returns (best_dsid, max_similarity) or (None, 0.0)."""
        best, best_score = None, -1.0
        for dsid, tpl in self.enrolled.items():
            s = cosine_similarity(probe, tpl)
            if s > best_score:
                best, best_score = dsid, s
        return best, best_score

    def decide(self, probe: list[float]) -> tuple[str | None, float, bool]:
        dsid, score = self.verify(probe)
        return dsid, score, (score >= self.threshold)


class SimMatcher(Matcher):
    """Score-drawing matcher for prototyping / fault injection.

    Genuine comparisons draw from N(mu_genuine, sigma); impostor from
    N(mu_impostor, sigma), clamped to [0,1].  Used to demonstrate threshold
    policy and feed the PAD + entitlement tests without a trained model.
    """

    def __init__(self, threshold: float, mu_genuine: float = 0.72,
                 mu_impostor: float = 0.45, sigma: float = 0.05,
                 rng=None):
        super().__init__(threshold)
        self.mu_genuine = mu_genuine
        self.mu_impostor = mu_impostor
        self.sigma = sigma
        self.rng = rng

    def _score(self, genuine: bool) -> float:
        import random
        r = self.rng or random
        mu = self.mu_genuine if genuine else self.mu_impostor
        return min(1.0, max(0.0, r.gauss(mu, self.sigma)))

    def verify(self, probe: list[float]) -> tuple[str, float]:
        # Simulation: probe content is ignored; call verify_controlled for
        # genuine/impostor semantics.  First enrolled entry wins.
        if not self.enrolled:
            return None, 0.0
        dsid = next(iter(self.enrolled))
        return dsid, self._score(False)

    def verify_controlled(self, dsid: str, genuine: bool) -> float:
        return self._score(genuine)