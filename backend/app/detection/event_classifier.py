"""Extreme weather vs sensor fault classification + false alarm guard (SIH 26073).

An unusual measurement is NOT automatically a sensor failure: a reading
is only attributed to the sensor when spatial isolation, abrupt/locked
temporal behaviour, broken physical coupling, or known degradation say
so. All verdicts derive from computed signals; nothing is hard-coded
per station or scenario.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.app.detection import features as F
from backend.app.detection.detectors import BOUNDS, RATE_LIMITS
from backend.app.detection.engine import DetectionResult

SENSORS = ("temperature", "pressure", "humidity")
EARTH_KM = 6371.0

# Expected standardized move for a genuine warm event: T up, H down,
# P slightly down. Multivariate coherence = alignment with this pattern.
EXPECTED_WARM_EVENT = {"temperature": 1.0, "pressure": -0.3, "humidity": -0.6}


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class EventClassification:
    event_type: str  # PROBABLE_SENSOR_FAULT | PROBABLE_WEATHER_EVENT | UNCERTAIN | NO_ANOMALY
    sensor_fault_probability: float
    weather_event_probability: float
    spatial_consistency: float
    temporal_consistency: float
    multivariate_consistency: float
    reasoning: list[str] = field(default_factory=list)
    factors: dict = field(default_factory=dict)


def _spatial(current: dict, neighbors: list[dict]) -> tuple[float, dict]:
    """Agreement of the station with nearby stations (0-1).

    Takes the MINIMUM over sensors: one wildly isolated channel means the
    station disagrees with its neighbourhood, even if other channels match.
    """
    cons, info = [], {}
    for s in SENSORS:
        v = current.get(s)
        nv = [n.get(s) for n in neighbors if not _missing(n.get(s))]
        if _missing(v) or len(nv) < 2:
            continue
        mean = sum(nv) / len(nv)
        std = math.sqrt(sum((x - mean) ** 2 for x in nv) / len(nv)) or 0.0
        floor = {"temperature": 0.5, "pressure": 1.0, "humidity": 2.0}[s]
        z = (v - mean) / max(std, floor)
        cons.append(1.0 / (1.0 + abs(z) / 2.0))
        info[s] = {"station": v, "neighbor_mean": round(mean, 2), "z": round(z, 2)}
    if not cons:
        return 0.5, {"unknown": "fewer than 2 neighbours with data"}
    return min(cons), info


def _shared_unusual(
    current: dict,
    neighbors: list[dict],
    history: list[dict],
    neighbor_histories: dict[str, list[dict]] | None = None,
) -> tuple[float, dict]:
    """Fraction of neighbours that are THEMSELVES unusual in the same direction.

    Preferred signal: each neighbour's own historical deviation (needs its
    history). Fallback without histories: deviation from the neighbour group
    mean (misses uniform shifts, noted in info).
    """
    v = current.get("temperature")
    if _missing(v):
        return 0.0, {"unknown": "station temperature missing"}
    feats = F.compute_latest([*history, current]) if history else {}
    own = feats.get("temperature_historical_deviation")
    own_sign = 1 if (own or 0) >= 0 else -1

    if neighbor_histories:
        scored = 0
        same = 0
        for n in neighbors:
            nh = (neighbor_histories or {}).get(n.get("station_id", ""), [])
            if len(nh) < 6 or _missing(n.get("temperature")):
                continue
            try:
                nf = F.compute_latest([*nh, {**n, "timestamp": current["timestamp"]}])
            except ValueError:
                continue
            hd = nf.get("temperature_historical_deviation")
            if hd is None or (isinstance(hd, float) and math.isnan(hd)):
                continue
            scored += 1
            if abs(hd) >= 2.0 and (1 if hd >= 0 else -1) == own_sign:
                same += 1
        if scored >= 2:
            return same / scored, {"same_direction": same, "neighbours": scored, "method": "own-history"}
    temps = [n.get("temperature") for n in neighbors if not _missing(n.get("temperature"))]
    if len(temps) < 2:
        return 0.0, {"unknown": "fewer than 2 neighbours with data"}
    mean = sum(temps) / len(temps)
    std = math.sqrt(sum((x - mean) ** 2 for x in temps) / len(temps))
    sign = 1 if v >= mean else -1
    same = sum(1 for x in temps if sign * (x - mean) > 2.0 * max(std, 0.5))
    return same / len(temps), {"same_direction": same, "neighbours": len(temps), "method": "group-mean"}


def _temporal(feats: dict) -> tuple[float, dict]:
    ratios = {}
    for s in SENSORS:
        r = feats.get(f"{s}_rate")
        if r is None or (isinstance(r, float) and math.isnan(r)):
            continue
        ratios[s] = abs(r) / RATE_LIMITS[s]
    worst = max(ratios.values()) if ratios else 0.0
    # Per-minute ratios are sampling-normalised: an hourly 23C jump still
    # only reaches ~2x, so the curve must bite early to flag abrupt onset.
    base = _clamp01(1.0 - worst / 3.0)
    streaks = {s: feats.get(f"{s}_identical_streak") or 0 for s in SENSORS}
    locked = max(streaks.values())
    if locked >= 6:
        base = min(base, 0.3)
    return base, {"rate_ratios": {k: round(v, 2) for k, v in ratios.items()}, "max_streak": locked}


def _multivariate(feats: dict) -> tuple[float, dict]:
    """Coherence of the joint T/H move: direction match PLUS coupled response.

    A lone-temperature jump with no humidity response contradicts the normal
    inverse T-H coupling just as much as a hot-and-humid move does, so both
    the pattern alignment (cosine) and the expected humidity response count.
    """
    o = {s: feats.get(f"{s}_deviation") for s in SENSORS}
    o = {s: (0.0 if v is None or (isinstance(v, float) and math.isnan(v)) else v) for s, v in o.items()}
    norm_o = math.sqrt(sum(v * v for v in o.values()))
    if norm_o == 0:
        return 1.0, {"note": "no joint move"}
    e = EXPECTED_WARM_EVENT
    norm_e = math.sqrt(sum(v * v for v in e.values()))
    cos = sum(o[s] * e[s] for s in SENSORS) / (norm_o * norm_e)
    direction = _clamp01((cos + 1.0) / 2.0)
    zt, zh = abs(o["temperature"]), o["humidity"]
    if zt < 1.0:
        response = 1.0  # no thermal move, nothing expected
    else:
        # Humidity should move opposite to temperature, proportionally.
        response = _clamp01(max(0.0, -math.copysign(1.0, o["temperature"]) * zh) / max(1.0, 0.5 * zt))
    mv = 0.5 * direction + 0.5 * response
    return mv, {"cosine": round(cos, 3), "response": round(response, 3)}


def _historical(feats: dict) -> tuple[float, dict]:
    vals = []
    for s in SENSORS:
        h = feats.get(f"{s}_historical_deviation")
        if h is None or (isinstance(h, float) and math.isnan(h)):
            continue
        vals.append(abs(h))
    if not vals:
        return 0.5, {"unknown": "no history"}
    worst = max(vals)
    return _clamp01(1.0 - worst / 6.0), {"max_hist_z": round(worst, 2)}


def _degradation(sensor_health: dict | None) -> tuple[float | None, dict]:
    if not sensor_health:
        return None, {"unknown": "no sensor-health data"}
    scores = [v for v in sensor_health.values() if isinstance(v, (int, float))]
    if not scores:
        return None, {"unknown": "no sensor-health data"}
    return _clamp01(1.0 - sum(scores) / len(scores) / 100.0), {"mean_health": round(sum(scores) / len(scores), 1)}


def classify_event(
    current: dict,
    history: list[dict],
    detection: DetectionResult,
    neighbors: list[dict] | None = None,
    sensor_health: dict | None = None,
    neighbor_histories: dict[str, list[dict]] | None = None,
) -> EventClassification:
    """Weather vs fault verdict from live signals. Probabilities sum to 1."""
    neighbors = neighbors or []
    reasoning: list[str] = []
    if detection.anomaly_type == "NORMAL":
        return EventClassification("NO_ANOMALY", 0.0, 0.0, 1.0, 1.0, 1.0, ["no anomaly detected"], {})

    feats = F.compute_latest([*history, current])
    spatial, spatial_info = _spatial(current, neighbors)
    shared, shared_info = _shared_unusual(current, neighbors, history, neighbor_histories)
    temporal, temporal_info = _temporal(feats)
    if shared >= 0.7:
        # A simultaneous region-wide jump is temporally coherent AS weather
        # (advection fronts move fast); abruptness only indicts isolated moves.
        temporal = max(temporal, 0.6)
        reasoning_note = "onset shared region-wide"
    else:
        reasoning_note = None
    multi, multi_info = _multivariate(feats)
    historical, historical_info = _historical(feats)
    degradation, health_info = _degradation(sensor_health)
    ml = _clamp01(detection.anomaly_score / 100.0)

    fault_parts = [1 - spatial, 1 - temporal, 1 - multi, 1 - historical, ml]
    if degradation is not None:
        fault_parts.append(degradation)
    # Weather evidence weights: sharing with neighbours dominates, because a
    # spatially shared move is the defining trait of a meteorological event.
    in_range = True
    for s in SENSORS:
        v = current.get(s)
        if _missing(v):
            continue
        lo, hi = BOUNDS[s]
        if not lo <= v <= hi:
            in_range = False
    weather = (
        0.35 * shared
        + 0.20 * temporal
        + 0.20 * multi
        + 0.10 * historical
        + 0.15 * (1.0 if in_range else 0.0)
    )

    fault = sum(fault_parts) / len(fault_parts)
    total = fault + weather
    pf = fault / total if total > 0 else 0.5
    pw = weather / total if total > 0 else 0.5

    # Persistent-state override: when the engine confirms a fault STATE
    # (frozen/drift/invalid/comm, score >= 50 from live detector evidence)
    # history-relative factors go quiet by construction (a stuck value equals
    # its own past), so the state evidence floors the fault probability —
    # unless neighbours share the identical state (network-wide replay/event).
    state_detector = {"FROZEN_SENSOR": "frozen", "SENSOR_DRIFT": "drift",
                      "INVALID_DATA": "physical"}.get(detection.anomaly_type)
    state_strength = 0.0
    if state_detector:
        for r in detection.detector_results:
            if r.name == state_detector and r.triggered:
                state_strength = max(state_strength, r.score / 100.0)
    elif detection.anomaly_type == "COMMUNICATION_FAILURE":
        state_strength = min(1.0, detection.anomaly_score / 100.0)
    if state_strength >= 0.5 and shared < 0.5:
        pf = max(pf, 0.5 + 0.5 * state_strength)
        pw = 1.0 - pf
        reasoning.append(
            f"Engine confirms a persistent fault state ({detection.anomaly_type.lower().replace('_', ' ')}, "
            f"strength {state_strength:.2f}) that neighbours do not share"
        )

    n_with_data = sum(1 for n in neighbors if not _missing(n.get("temperature")))
    t = current.get("temperature")
    if "z" in spatial_info.get("temperature", {}):
        ti = spatial_info["temperature"]
        reasoning.append(
            f"Temperature {t}C deviates {abs(ti['z']):.1f} sigma from {n_with_data} neighbours (mean {ti['neighbor_mean']}C)"
        )
    else:
        reasoning.append(f"Spatial check inconclusive ({spatial_info})")
    if shared_info.get("neighbours"):
        reasoning.append(
            f"{shared_info['same_direction']}/{shared_info['neighbours']} neighbours deviate the same way"
        )
    reasoning.append(
        f"Temporal consistency {temporal:.2f} (worst rate ratio {max(temporal_info['rate_ratios'].values()) if temporal_info['rate_ratios'] else 0:.1f}x synoptic limit"
        + (f"; {reasoning_note}" if reasoning_note else "") + ")"
    )
    reasoning.append(f"Multivariate coherence {multi:.2f} (pattern cosine {multi_info.get('cosine', 'n/a')})")
    reasoning.append(
        f"Sensor degradation {degradation:.2f}" if degradation is not None else "Sensor health unknown"
    )
    reasoning.append(f"ML anomaly score {detection.anomaly_score:.1f}/100 ({detection.anomaly_type})")

    margin = abs(pf - pw)
    if margin < 0.15:
        etype = "UNCERTAIN"
        reasoning.append(f"Evidence is balanced (margin {margin:.2f}); cannot separate fault from event")
    elif pf > pw:
        etype = "PROBABLE_SENSOR_FAULT"
    else:
        etype = "PROBABLE_WEATHER_EVENT"

    return EventClassification(
        event_type=etype,
        sensor_fault_probability=round(pf, 3),
        weather_event_probability=round(pw, 3),
        spatial_consistency=round(spatial, 3),
        temporal_consistency=round(temporal, 3),
        multivariate_consistency=round(multi, 3),
        reasoning=reasoning,
        factors={
            "fault_score": round(fault, 3),
            "weather_score": round(weather, 3),
            "shared_unusual_fraction": round(shared, 3),
            # Regional consistency is the same shared-neighbour signal, named
            # for the spatial module/API; the classifier already fuses it into
            # weather_score (weight 0.35) and the simultaneity floor.
            "regional_consistency": round(shared, 3),
            "regional_band": "HIGH" if shared >= 0.50 and shared_info.get("neighbours", 0) >= 2
            else ("MEDIUM" if shared >= 0.25 and shared_info.get("neighbours", 0) >= 2
                  else ("LOW" if shared_info.get("neighbours", 0) >= 2 else "UNKNOWN")),
            "historical_consistency": round(historical, 3),
            "degradation": degradation,
            "in_range": in_range,
            "spatial_info": spatial_info,
        },
    )


@dataclass
class GuardVerdict:
    verdict: str  # CONFIRMED | LIKELY_FALSE_ALARM | UNCERTAIN
    recommend_suppress: bool
    passed: list[str]
    failed: list[str]
    details: dict


def guard_check(
    current: dict,
    history: list[dict],
    detection: DetectionResult,
    neighbors: list[dict] | None = None,
    sensor_health: dict | None = None,
) -> GuardVerdict:
    """Six independent validity checks; suppress only when everything benign."""
    neighbors = neighbors or []
    feats = F.compute_latest([*history, current]) if history else {}
    passed, failed, details = [], [], {}

    # 1. Physical possibility (absolute bounds)
    impossible = {}
    for s in SENSORS:
        v = current.get(s)
        if _missing(v):
            continue
        lo, hi = BOUNDS[s]
        if not lo <= v <= hi:
            impossible[s] = v
    details["physical"] = {"impossible": impossible}
    (failed if impossible else passed).append("physical_possibility")

    # 2. Temporal behaviour (gradual, not frozen)
    temporal, tinfo = _temporal(feats) if feats else (0.5, {})
    details["temporal"] = {"consistency": temporal, **tinfo}
    (passed if temporal >= 0.4 else failed).append("temporal_behavior")

    # 3. Multivariate relationship (physics coherent)
    multi, minfo = _multivariate(feats) if feats else (0.5, {})
    details["multivariate"] = {"coherence": multi, **minfo}
    (passed if multi >= 0.4 else failed).append("multivariate_relationship")

    # 4. Neighbour agreement (shared => real event, not instrument glitch).
    # With no neighbours in range the check abstains (neither pass nor fail).
    spatial, sinfo = _spatial(current, neighbors)
    shared, shinfo = _shared_unusual(current, neighbors, history)
    details["neighbors"] = {"spatial_consistency": spatial, "shared_fraction": shared, **shinfo}
    if not neighbors:
        details["neighbors"]["abstained"] = "no neighbours in range"
    elif spatial >= 0.4 or shared >= 0.5:
        passed.append("neighbor_agreement")
    else:
        failed.append("neighbor_agreement")

    # 5. Historical behaviour (precedented magnitude)
    historical, hinfo = _historical(feats) if feats else (0.5, {})
    details["historical"] = {"consistency": historical, **hinfo}
    (passed if historical >= 0.25 else failed).append("historical_behavior")

    # 6. Sensor degradation (chronically bad sensor => fault alert, still real)
    degradation, dhinfo = _degradation(sensor_health)
    details["health"] = {"degradation": degradation, **dhinfo}
    if degradation is None or degradation < 0.6:
        passed.append("sensor_degradation")
    else:
        failed.append("sensor_degradation")

    hard_fault = bool(impossible) or any(
        (feats.get(f"{s}_identical_streak") or 0) >= 12 for s in SENSORS
    )
    degraded = (degradation or 0) >= 0.6
    unprecedented = historical < 0.25
    benign = len(passed)
    score = detection.anomaly_score
    if hard_fault:
        verdict, suppress = "CONFIRMED", False
    elif degraded and unprecedented and score >= 50:
        # Chronically bad sensor producing unprecedented readings: the fault
        # alert itself is genuine (maintenance is really needed).
        verdict, suppress = "CONFIRMED", False
    elif benign >= 5 and score < 70:
        verdict, suppress = "LIKELY_FALSE_ALARM", True
    elif benign >= 4 and score < 50:
        verdict, suppress = "LIKELY_FALSE_ALARM", True
    elif benign <= 2:
        verdict, suppress = "CONFIRMED", False
    else:
        verdict, suppress = "UNCERTAIN", False
    return GuardVerdict(verdict, suppress, passed, failed, details)
