"""Explainable AI: WHY WAS THIS FLAGGED?

Every sentence is rendered from live detector/classifier outputs — no
canned per-scenario text. Attribution is exact, not approximated:

- Detector contributions are the additive decomposition of the fused
  score (weight x score, renormalised). For a weighted fusion this is
  faithful by construction, unlike post-hoc approximations.
- Feature contributions are shares of absolute standardized deviation.

A note on SHAP: the `shap` package is installed, but SHAP's TreeExplainer
does not support IsolationForest (isolation trees expose no compatible
decision paths), and KernelExplainer would re-fit the forest ~100x per
request for an approximation of a quantity we can compute exactly. Where
a tree/linear model is added later, plug its explainer into
`model_feature_contributions()` — the hook is provided below.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.app.detection import features as F
from backend.app.detection.detectors import DEFAULT_WEIGHTS
from backend.app.detection.engine import DetectionResult
from backend.app.detection.event_classifier import EventClassification

try:
    import shap  # noqa: F401  (capability flag only; see module docstring)

    SHAP_AVAILABLE = True
except ImportError:  # pragma: no cover
    SHAP_AVAILABLE = False

ATTRIBUTION_METHOD = "exact_fusion_decomposition"

UNITS = {"temperature": "C", "pressure": "hPa", "humidity": "%"}
PRETTY = {"temperature": "Temperature", "pressure": "Pressure", "humidity": "Humidity"}

ACTION_BY_TYPE = {
    "FROZEN_SENSOR": "Inspect the sensor for sticking, ice, debris or power issues; compare against a handheld reference and replace if it remains locked.",
    "SENSOR_DRIFT": "Schedule recalibration of the drifting sensor against a reference standard; review calibration logs for gradual bias.",
    "TEMPERATURE_SPIKE": "Verify the temperature probe and its shielding/aspiration; check for local heat sources or exposure changes.",
    "TEMPERATURE_DROP": "Verify the temperature probe and wiring; check for shading, water ingress or exposure changes.",
    "PRESSURE_ANOMALY": "Verify the barometer port for blockages and check temperature compensation; compare with a reference barometer.",
    "HUMIDITY_ANOMALY": "Verify the humidity probe for contamination or saturation; clean or replace the filter cap.",
    "MULTIVARIATE_INCONSISTENCY": "Cross-check all three probes together; a joint inconsistency often means one failing channel corrupting derived products.",
    "INVALID_DATA": "Reject the reading for downstream use; inspect the station for hardware or transmission faults.",
    "MISSING_DATA": "Check power and telemetry links; backfill from logger memory if available.",
    "COMMUNICATION_FAILURE": "Check power, modem and antenna; dispatch communications maintenance if the gap persists.",
}

ACTION_BY_EVENT = {
    "PROBABLE_SENSOR_FAULT": "Treat downstream products using this station with caution until the sensor is verified.",
    "PROBABLE_WEATHER_EVENT": "No maintenance needed; escalate to forecasters for nowcasting and public guidance.",
    "UNCERTAIN": "Keep the station under watch; re-evaluate when the next observations arrive.",
    "NO_ANOMALY": "No action required.",
}


@dataclass
class Explanation:
    station_id: str
    anomaly_type: str
    anomaly_score: float
    severity: str
    confidence: float
    root_cause: str
    event_type: str | None
    main_reason: str
    conclusion: str
    supporting_evidence: list[str] = field(default_factory=list)
    contributing_features: list[dict] = field(default_factory=list)
    methods_triggered: list[dict] = field(default_factory=list)
    recommended_action: str = ""
    attribution_method: str = ATTRIBUTION_METHOD
    shap_available: bool = SHAP_AVAILABLE


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _fmt(v: float) -> str:
    return f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"


def detector_contributions(detection: DetectionResult, weights: dict | None = None) -> list[dict]:
    """Exact additive share of each detector in the fused score."""
    weights = weights or DEFAULT_WEIGHTS
    ran = [r for r in detection.detector_results if "skipped" not in r.evidence]
    wsum = sum(weights.get(r.name, 0.0) for r in ran) or 1.0
    out = []
    for r in ran:
        contrib = r.score * weights.get(r.name, 0.0) / wsum
        out.append(
            {
                "detector": r.name,
                "score": round(r.score, 2),
                "weight": weights.get(r.name, 0.0),
                "contribution": round(contrib, 2),
                "triggered": r.triggered,
                "method": ATTRIBUTION_METHOD,
            }
        )
    out.sort(key=lambda d: d["contribution"], reverse=True)
    return out


def model_feature_contributions(feats: dict) -> list[dict]:
    """Genuine per-feature contributions from standardized deviations.

    Hook for SHAP: when a SHAP-compatible model (tree/linear) is added to
    the ensemble, compute its SHAP values here and merge them with these
    deviation shares. IsolationForest has no compatible SHAP explainer,
    so deviation shares are the faithful signal today.
    """
    scored = []
    for s in ("temperature", "pressure", "humidity"):
        z = feats.get(f"{s}_deviation")
        if z is None or (isinstance(z, float) and math.isnan(z)):
            continue
        scored.append(
            {
                "feature": f"{s}_deviation",
                "sensor": s,
                "value": feats.get(f"{s}_deviation"),
                "baseline": feats.get(f"{s}_rolling_mean"),
                "z_score": round(z, 2),
                "abs_z": abs(z),
                "method": ATTRIBUTION_METHOD,
            }
        )
    total = sum(c["abs_z"] for c in scored) or 1.0
    for c in scored:
        c["contribution"] = round(c["abs_z"] / total * 100.0, 2)
        del c["abs_z"]
    scored.sort(key=lambda c: c["contribution"], reverse=True)
    return scored


def _describe_move(current: dict, history: list[dict], feats: dict) -> str:
    from datetime import timezone

    sensor = None
    best = 0.0
    for s in ("temperature", "pressure", "humidity"):
        ch = feats.get(f"{s}_change")
        if ch is not None and abs(ch) > best:
            best, sensor = abs(ch), s
    dt_min = None
    if history:
        last_ts = history[-1]["timestamp"]
        cur_ts = current["timestamp"]
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        if cur_ts.tzinfo is None:
            cur_ts = cur_ts.replace(tzinfo=timezone.utc)
        dt_min = (cur_ts - last_ts).total_seconds() / 60.0
    when = f" within {dt_min:.0f} minutes" if dt_min else ""
    if sensor is None:
        return "No measurable single-step move; the anomaly comes from persistent or joint behaviour."
    ch = feats[f"{sensor}_change"]
    direction = "increased" if ch > 0 else "decreased"
    unit = UNITS[sensor]
    z = feats.get(f"{sensor}_deviation")
    base = feats.get(f"{sensor}_rolling_mean")
    text = f"{PRETTY[sensor]} {direction} by {abs(ch):.1f}{unit}{when}."
    if z is not None and base is not None:
        text += f" This is {abs(z):.1f} standard deviations from its recent mean of {base:.1f}{unit}."
    return text


def build_explanation(
    current: dict,
    history: list[dict],
    detection: DetectionResult,
    classification: EventClassification | None = None,
    guard=None,
    neighbors: list[dict] | None = None,
    anomaly_id: int | None = None,
) -> Explanation:
    """Assemble the full WHY explanation from live results."""
    feats = F.compute_latest([*history, current]) if history else {}
    atype = detection.anomaly_type
    methods = detector_contributions(detection)
    fired = [m for m in methods if m["triggered"]]
    features = model_feature_contributions(feats) if feats else []

    # Main reason depends on the anomaly family, numbers always live.
    if atype in ("MISSING_DATA", "COMMUNICATION_FAILURE"):
        ev = detection.evidence or {}
        main = f"No usable measurement arrived (gap streak {ev.get('gap_streak', '?')} intervals)."
    elif atype == "INVALID_DATA":
        viol = []
        for r in detection.detector_results:
            for s, d in (r.evidence.get("violations") or {}).items():
                viol.append(f"{s}={d['value']} outside [{d['bounds'][0]},{d['bounds'][1]}]")
        main = "Reading violates physical plausibility: " + ("; ".join(viol) or "out-of-range value") + "."
    elif atype == "FROZEN_SENSOR":
        streaks = {}
        for r in detection.detector_results:
            if r.name == "frozen":
                streaks = r.evidence.get("streaks", {})
        stuck = ", ".join(f"{s} ({n} repeats)" for s, n in streaks.items() if n and n >= 6) or "sensor locked"
        main = f"Sensor output is stuck: {stuck} with no natural variation."
    elif atype == "SENSOR_DRIFT":
        slopes = {}
        for r in detection.detector_results:
            if r.name == "drift":
                slopes = r.evidence.get("slopes", {})
        parts = ", ".join(f"{s} {d['slope_per_step']:+.2f}/step" for s, d in slopes.items()) or "sustained slope"
        main = f"Gradual calibration drift detected: {parts} over recent readings."
    else:
        main = _describe_move(current, history, feats) if feats else "Anomalous joint behaviour."

    supporting: list[str] = []
    if feats:
        dist = feats.get("multivariate_distance")
        if dist is not None and dist >= 2.0:
            supporting.append(f"Joint T/H/P move is {dist:.1f} sigma from recent behaviour (multivariate).")
        th = feats.get("temperature_humidity_relationship")
        if th is not None and th > 1.0:
            supporting.append(
                f"Temperature-humidity coupling is abnormal (co-deviation product {th:.1f}; these normally move inversely)."
            )
    if classification is not None:
        supporting.extend(classification.reasoning)
    if_fired = next((m for m in methods if m["detector"] == "isolation_forest" and m["triggered"]), None)
    if if_fired:
        supporting.append(
            f"The ML detector also classified the observation as an outlier (score {if_fired['score']:.1f}/100)."
        )
    if guard is not None and getattr(guard, "failed", None):
        if guard.failed:
            supporting.append(f"False-alarm guard failed checks: {', '.join(guard.failed)}.")
    if not supporting:
        supporting.append("Flagged by detector consensus without a single dominant signature.")

    etype = classification.event_type if classification else None
    if etype == "PROBABLE_SENSOR_FAULT":
        conclusion = f"Conclusion: probable sensor anomaly ({atype.lower().replace('_', ' ')})."
    elif etype == "PROBABLE_WEATHER_EVENT":
        conclusion = "Conclusion: probable genuine meteorological event; sensors appear healthy."
    elif etype == "UNCERTAIN":
        conclusion = "Conclusion: evidence is mixed; keep under watch and re-evaluate on next readings."
    else:
        conclusion = f"Conclusion: {atype.lower().replace('_', ' ')}."

    action = ACTION_BY_TYPE.get(atype, "Review the flagged readings and station maintenance log.")
    if etype in ACTION_BY_EVENT:
        action += " " + ACTION_BY_EVENT[etype]

    return Explanation(
        station_id=current.get("station_id", ""),
        anomaly_type=atype,
        anomaly_score=detection.anomaly_score,
        severity=detection.severity,
        confidence=detection.confidence,
        root_cause=atype,
        event_type=etype,
        main_reason=main,
        conclusion=conclusion,
        supporting_evidence=supporting,
        contributing_features=features,
        methods_triggered=fired,
        recommended_action=action,
    )


def compact_explanation(exp: Explanation, top_n: int = 3) -> dict:
    """Small JSON-safe form stored inside the anomaly evidence column."""
    return {
        "main_reason": exp.main_reason,
        "conclusion": exp.conclusion,
        "root_cause": exp.root_cause,
        "event_type": exp.event_type,
        "recommended_action": exp.recommended_action,
        "top_contributors": exp.contributing_features[:top_n],
        "methods_triggered": [m["detector"] for m in exp.methods_triggered],
    }
