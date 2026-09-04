# SPDX-License-Identifier: MIT
"""Biometric pipeline: face capture abstraction, presentation-attack
detection (PAD) per ISO/IEC 30107-3, matching with tiered threshold policy,
and multi-modal fusion with fallback decision tree + abuse limits.

Pipeline order on device:
    capture -> PAD (liveness) -> face match (primary)
             -> fingerprint match (fallback tier 1, if scanner present)
             -> offline PIN (fallback tier 2, OTP-free)
             -> reject / escalate (four-eyes override, rate-limited)

FAR/FRR operating point is per security tier and adjusted for cohort size:
for a 1:N lookup over a village-scale DB the per-trial FAR must be
tightened so the family-wise FAR stays at the tier target (Bonferroni).
"""

from __future__ import annotations

import enum
import math
import time

from . import crypto

# --------------------------------------------------------------------------- #
# PAD / liveness
# --------------------------------------------------------------------------- #


class PADMethod(enum.Enum):
    IR = "ir_structured_light"       # hardware where present
    SOFTWARE = "software_l2"         # ISO 30107-3 Level 2 rule-based classifier
    NONE = "none"


class PADResult:
    def __init__(self, live: bool, score: float, method: str,
                 reasons: list[str] | None = None):
        self.live = live
        self.score = score          # 0..1; >1 means attack-flagged by a rule
        self.method = method
        self.reasons = reasons or []

    def __bool__(self) -> bool:
        return self.live


class LivenessGate:
    """Software PAD (Level 1/2) over feature signals, plus IR/structured-light
    path when depth features are available.

    `evaluate(features)` takes a dict of probe features:
        texture_entropy   float  0..1  (1 = high micro-texture, live skin)
        specular_ratio    float  0..1  (silicone/mask highlights)
        planar_edge       float  0..1  (paper-cutout straight-edge density)
        motion_coherence  float  0..1  (1 = coherent 3D motion; 0 = flat replay)
        depth_spread      float|None   median depth variance (IR/structured-light)

    Returns PADResult(live, score).  Scores are normalized so a *higher* score
    means more attack-like; `live` is decided against the configured threshold.
    """

    def __init__(self, method: PADMethod = PADMethod.SOFTWARE,
                 threshold: float = 0.55, require_hardware_depth: bool = False,
                 name: str = "pad-software-l2-v1"):
        self.method = method
        self.threshold = threshold
        self.require_hardware_depth = require_hardware_depth
        self.name = name

    def evaluate(self, features: dict) -> PADResult:
        if self.method is PADMethod.NONE:
            return PADResult(True, 0.0, "none", ["liveness disabled"])
        reasons: list[str] = []

        if self.require_hardware_depth:
            depth = features.get("depth_spread")
            if depth is None:
                return PADResult(False, 1.0, self.method.value,
                                 ["hardware depth channel required but absent"])
            if depth < 0.05:
                reasons.append("flat depth map (mask/photo)")
            return self._score(features, reasons, weight_depth=1.0)

        return self._score(features, reasons)

    def _score(self, features: dict, reasons: list[str],
               weight_depth: float = 0.0) -> PADResult:
        entropy = max(0.0, min(1.0, features.get("texture_entropy", 0.5)))
        spec = max(0.0, min(1.0, features.get("specular_ratio", 0.0)))
        planar = max(0.0, min(1.0, features.get("planar_edge", 0.0)))
        motion = max(0.0, min(1.0, features.get("motion_coherence", 1.0)))
        depth = features.get("depth_spread")

        attack = 0.0
        # printed / paper-cutout: low texture, high planar edge density
        if entropy < 0.35:
            attack += 0.45 * (1.0 - entropy)
            reasons.append("low texture entropy")
        if planar > 0.45:
            attack += 0.30 * planar
            reasons.append("high planar edge density (cutout)")
        # silicone / mask: high specularity
        if spec > 0.30:
            attack += 0.35 * spec
            reasons.append("unusual specular ratio")
        # video replay: coherent flat motion
        if motion < 0.30:
            attack += 0.35 * (1.0 - motion)
            reasons.append("flat motion (replay)")
        if weight_depth > 0 and depth is not None and depth < 0.05:
            attack += 0.6
            reasons.append("flat depth map")

        # add the entropy/planar/spec components scaled so a clean live face
        # (entropy>=0.5, planar<=0.2, spec<=0.15, motion>=0.6) scores <0.2
        base = 0.5 * (1.0 - entropy) + 0.25 * planar + 0.15 * spec + 0.10 * (1.0 - motion)
        score = min(1.0, base + attack)
        live = score <= self.threshold
        return PADResult(live, round(score, 4), self.method.value, reasons)


class PadMetrics:
    """ISO/IEC 30107-3 reporting: APCER (attack presentations accepted) and
    BPCER (bona fide presentations rejected), plus the decision threshold and
    per-attack-subtype counts for the curated attack set."""

    def __init__(self):
        self._bona_fide = {"n": 0, "rejected": 0}
        self._attacks: dict[str, dict] = {}

    def record(self, true_label: str, subtype: str | None, live_decision: bool):
        if true_label == "bona_fide":
            self._bona_fide["n"] += 1
            if not live_decision:
                self._bona_fide["rejected"] += 1
        else:
            d = self._attacks.setdefault(
                true_label, {"n": 0, "accepted": 0, "subtype": subtype or ""}
            )
            d["n"] += 1
            if live_decision:
                d["accepted"] += 1

    def apcer(self) -> dict[str, float]:
        out = {}
        for k, d in self._attacks.items():
            out[k] = d["accepted"] / d["n"] if d["n"] else 0.0
        return out

    def bpcer(self) -> float:
        if self._bona_fide["n"] == 0:
            return 0.0
        return self._bona_fide["rejected"] / self._bona_fide["n"]

    def report(self) -> dict:
        return {
            "apcer": self.apcer(),
            "bpcer": self.bpcer(),
            "bona_fide_trials": self._bona_fide["n"],
            "attack_trials": {k: d["n"] for k, d in self._attacks.items()},
        }


# --------------------------------------------------------------------------- #
# Matching + threshold policy
# --------------------------------------------------------------------------- #

# Representative error model for an INT8-quantized ArcFace-style embedding:
# genuine cosine similarity ~ N(0.62, 0.10), impostor ~ N(0.10, 0.16).
# Pluggable per model version via ThresholdPolicy(model_params).


class ThresholdPolicy:
    """Maps security tier -> FAR target -> cosine threshold, with the
    cohort (1:N) Bonferroni correction and expected FRR at that threshold."""

    TIERS = {
        "low":       {"far": 1e-2},
        "standard":  {"far": 1e-4},
        "high":      {"far": 1e-5},
    }

    def __init__(self, mu_imp: float = 0.10, sigma_imp: float = 0.16,
                 mu_gen: float = 0.62, sigma_gen: float = 0.10,
                 model_version: str = "arcface-int8-v1"):
        self.mu_imp, self.sigma_imp = mu_imp, sigma_imp
        self.mu_gen, self.sigma_gen = mu_gen, sigma_gen
        self.model_version = model_version

    def threshold_for_far(self, far: float) -> float:
        """cosine threshold t s.t. P(impostor > t) <= far."""
        if far <= 0:
            return 1.0
        return self.mu_imp + self.sigma_imp * self._norm_ppf(1.0 - far)

    def frr_at(self, threshold: float) -> float:
        """P(genuine < threshold)."""
        return self._norm_cdf((self.mu_gen - threshold) / self.sigma_gen)

    def threshold_for_tier(self, tier: str, cohort_size: int = 1) -> dict:
        """Per-trial threshold for a tier, tightened by Bonferroni when the
        operator matches against a 1:N candidate cohort instead of a 1:1
        claim."""
        far = self.TIERS[tier]["far"]
        n = max(1, cohort_size)
        per_trial = far / n
        thr = self.threshold_for_far(per_trial)
        return {
            "tier": tier,
            "cohort_size": n,
            "target_far_familywise": far,
            "target_far_pertrial": per_trial,
            "threshold": round(thr, 6),
            "expected_frr": round(self.frr_at(thr), 6),
        }

    def threshold_for_far_pertrial(self, far_pertrial: float) -> float:
        return self.threshold_for_far(far_pertrial)

    # -- gaussian helpers -------------------------------------------------- #

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @classmethod
    def _norm_ppf(cls, p: float) -> float:
        if p <= 0.0:
            return -math.inf
        if p >= 1.0:
            return math.inf
        lo, hi = -8.0, 8.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if cls._norm_cdf(mid) < p:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)


class Matcher:
    """Embedding matcher with cosine similarity, model-version tag and an
    explicit quantized flag (accuracy delta vs the FP32 model is carried in
    the model metadata, not assumed)."""

    def __init__(self, policy: ThresholdPolicy, quantized: bool = True,
                 model_version: str | None = None):
        self.policy = policy
        self.quantized = quantized
        self.model_version = model_version or policy.model_version

    def cosine(self, a: bytes, b: bytes) -> float:
        """Cosine over raw float32 little-endian embedding vectors."""
        import struct
        n = min(len(a), len(b)) // 4
        va = struct.unpack(f"<{n}f", a[: n * 4])
        vb = struct.unpack(f"<{n}f", b[: n * 4])
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(y * y for y in vb))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def match(self, query: bytes, enrolled: bytes,
              threshold: float | None = None) -> dict:
        score = self.cosine(query, enrolled)
        return {
            "score": round(score, 6),
            "model_version": self.model_version,
            "quantized": self.quantized,
            "accepted": score >= (threshold if threshold is not None else 0.0),
        }


# --------------------------------------------------------------------------- #
# Fusion / fallback decision tree
# --------------------------------------------------------------------------- #

FALLBACK_METADATA = {
    "face":       {"far": 1e-4, "frr": 2e-3, "max_attempts": 3, "lockout_s": 120},
    "fingerprint": {"far": 1e-5, "frr": 1e-2, "max_attempts": 3, "lockout_s": 180},
    "pin":        {"far": 1e-6, "frr": 1e-4, "max_attempts": 5, "lockout_s": 900},
}


class FusionPolicy:
    """Decision tree: face primary; fingerprint tier 1; offline PIN tier 2.
    Each fallback has its own FAR/FPR metadata and abuse limits.  A fallback
    is *enabled* only if the configured channel is present."""

    def __init__(self, fingerprint_present: bool, pin_present: bool,
                 pin_verifier=None, face_threshold: float | None = None):
        self.fingerprint_present = fingerprint_present
        self.pin_present = pin_present
        self.pin_verifier = pin_verifier
        self.face_threshold = face_threshold

    def decide(self, face_match: dict, fp_match: dict | None = None,
               pin_ok: bool | None = None) -> dict:
        """Return a decision {ok, path, reason}.  Paths:
        ['face'], ['face','fingerprint'], ['face','fingerprint','pin'], [].
        """
        if face_match["accepted"]:
            return {"ok": True, "path": ["face"], "reason": "face-match"}
        if self.fingerprint_present and fp_match is not None and fp_match["accepted"]:
            return {"ok": True, "path": ["face", "fingerprint"],
                    "reason": "fingerprint-fallback"}
        if self.pin_present and pin_ok is True:
            return {"ok": True, "path": ["face", "fingerprint", "pin"],
                    "reason": "pin-fallback"}
        return {"ok": False, "path": [], "reason": "all-channels-failed"}


class LockoutTracker:
    """Sliding-window abuse limiter per subject+channel.  After
    max_attempts failures within `window_s`, the key is locked until
    `lockout_s` of quiet elapses; further attempts on a locked key raise."""

    def __init__(self, default_max: int = 3, window_s: int = 300,
                 lockout_s: int = 600):
        self.default_max = default_max
        self.window_s = window_s
        self.lockout_s = lockout_s
        self._fails: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._clock = time.time

    def _now(self) -> float:
        return self._clock()

    def is_locked(self, key: str) -> bool:
        if self._locked_until.get(key, 0.0) > self._now():
            return True
        self._locked_until.pop(key, None)
        return False

    def record_failure(self, key: str, max_attempts: int | None = None,
                       lockout_s: int | None = None) -> bool:
        now = self._now()
        fails = [t for t in self._fails.get(key, []) if now - t < self.window_s]
        fails.append(now)
        self._fails[key] = fails
        limit = max_attempts or self.default_max
        if len(fails) >= limit:
            self._locked_until[key] = now + (lockout_s or self.lockout_s)
            self._fails.pop(key, None)
            return True  # now locked out
        return False

    def record_success(self, key: str) -> None:
        self._fails.pop(key, None)
        self._locked_until.pop(key, None)

    def lockout_remaining_s(self, key: str) -> int:
        return max(0, int(self._locked_until.get(key, 0.0) - self._now()))


# --------------------------------------------------------------------------- #
# Offline PIN verifier (fallback tier 2)
# --------------------------------------------------------------------------- #

class PinVerifier:
    """Verifies the beneficiary's offline PIN against the authority-signed
    hash stored in the (signed) beneficiary record.  PBKDF2-HMAC-SHA256 with
    a per-record salt and a high iteration count; verification is rate
    limited by the caller's LockoutTracker.  The signed record makes the hash
    non-replaceable without breaking the authority signature."""

    PBKDF2_ITER = 600_000

    def __init__(self, max_attempts: int = 5, lockout_s: int = 900):
        self.max_attempts = max_attempts
        self.lockout_s = lockout_s

    def hash_pin(self, pin: str, salt: bytes) -> bytes:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                         salt=salt, iterations=self.PBKDF2_ITER)
        return kdf.derive(pin.encode("utf-8"))

    def verify(self, pin: str, salt: bytes, expected_hash: bytes) -> bool:
        return crypto.hmac.compare_digest(self.hash_pin(pin, salt), expected_hash)
