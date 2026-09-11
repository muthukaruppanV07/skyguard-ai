"""Real-time AWS simulation engine: physics -> REAL pipeline per tick.

Every emitted observation flows through the genuine stack — hybrid
detection engine, event classifier, guard, explainer, health recompute,
alert persistence. Nothing is synthesized at the output side: anomaly
scores, classifications and explanations are computed, never staged.

Tick cadence is simulated time (default 60 min per tick); the background
loop paces wall-clock delivery. `tick()` also works standalone (manual
stepping, used by tests) regardless of run state.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.app.detection.engine import HybridEngine
from backend.app.detection.event_classifier import classify_event, guard_check
from backend.app.explainability.explainer import build_explanation
from backend.app.health.engine import recompute_and_store as recompute_health
from backend.app.models.observation import Observation
from backend.app.services.detection_service import (
    load_history,
    load_sensor_health,
    persist_detection,
    raise_alert,
)
from backend.app.simulation.dataset_generator import _clean_physics, STATION_CLIMATE

STOPPED, RUNNING, PAUSED = "STOPPED", "RUNNING", "PAUSED"

SCENARIO_IDS = [
    "normal", "temp_spike", "temp_drop", "frozen", "drift",
    "pressure", "humidity", "missing", "comm_failure", "multivariate",
    "extreme_weather", "multi_station_event", "multi_failure",
]

SCENARIO_INFO = {
    "normal": "Normal weather, no faults",
    "temp_spike": "Sudden temperature jump on target station",
    "temp_drop": "Sudden temperature drop on target station",
    "frozen": "Sensor locks at a constant value",
    "drift": "Gradual temperature calibration drift",
    "pressure": "Sudden pressure jump on target station",
    "humidity": "Sudden humidity excursion on target station",
    "missing": "Short data gap (no emission)",
    "comm_failure": "Extended outage burst (no emission)",
    "multivariate": "Physically incoherent hot-and-humid move",
    "extreme_weather": "Coherent hot-dry burst on target station",
    "multi_station_event": "Coherent weather burst on ALL stations",
    "multi_failure": "Frozen + drift + spike on three stations at once",
}


@dataclass
class ActiveScenario:
    scenario_id: str
    targets: list[str]
    ticks_left: int
    magnitude: float = 1.0
    state: dict = field(default_factory=dict)


@dataclass
class StationState:
    station_id: str
    latitude: float
    longitude: float
    rng: random.Random
    physics: dict = field(default_factory=dict)
    ts: datetime | None = None
    skip_streak: int = 0
    last_value: dict = field(default_factory=dict)


class SimulationEngine:
    def __init__(self, session_factory, stations: list[dict],
                 step_minutes: int = 60, tick_interval_s: float = 1.0,
                 seed: int = 42, start: datetime | None = None,
                 emit_system_alerts: bool = True):
        self.session_factory = session_factory
        self.step = timedelta(minutes=step_minutes)
        self.tick_interval_s = tick_interval_s
        self.seed = seed
        # Default clock is wall time so streamed rows always extend real history.
        # A fixed past start would place new rows behind existing data and
        # corrupt trailing-window features (rates, drift, rolling stats).
        self.start_ts = start or datetime.now(timezone.utc)
        self.stations: dict[str, StationState] = {}
        for i, s in enumerate(stations):
            self.stations[s["station_id"]] = StationState(
                station_id=s["station_id"], latitude=s["latitude"], longitude=s["longitude"],
                rng=random.Random(seed + i), ts=self.start_ts,
            )
        self.status = STOPPED
        self.tick_count = 0
        self.active: ActiveScenario | None = None
        self.engine = HybridEngine()
        self.subscribers: set = set()
        self._task: asyncio.Task | None = None
        self.emit_system_alerts = emit_system_alerts

    def _system_alert(self, text: str) -> None:
        """Fire-and-forget SYSTEM alert row (lifecycle events are backend-generated)."""
        if not self.emit_system_alerts:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _store():
            from backend.app.models.alert import Alert

            async with self.session_factory() as session:
                session.add(Alert(station_id="SYSTEM", anomaly_id=None,
                                  severity="SYSTEM", message=text))
                await session.commit()

        loop.create_task(_store())

    # ---- controls ----
    def start(self):
        if self.status != RUNNING:
            self.status = RUNNING
            self._system_alert("Simulation streaming started")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._loop())

    def pause(self):
        if self.status == RUNNING:
            self.status = PAUSED

    def resume(self):
        if self.status == PAUSED:
            self.status = RUNNING

    async def stop(self):
        self.status = STOPPED
        self._system_alert(f"Simulation stopped at tick {self.tick_count}")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def reset(self):
        self.active = None
        self.tick_count = 0
        for i, st in enumerate(self.stations.values()):
            st.rng = random.Random(self.seed + i)
            st.ts = self.start_ts
            st.physics = {}
            st.skip_streak = 0
            st.last_value = {}

    def inject(self, scenario_id: str, station_ids: list[str] | None = None,
               duration_ticks: int | None = None, magnitude: float = 1.0):
        if scenario_id not in SCENARIO_IDS:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        ids = list(self.stations)
        if scenario_id == "multi_station_event":
            targets = ids
        elif scenario_id == "multi_failure":
            targets = ids[:3]
        elif station_ids:
            unknown = set(station_ids) - set(ids)
            if unknown:
                raise ValueError(f"Unknown stations: {sorted(unknown)}")
            targets = station_ids
        else:
            targets = [ids[1] if len(ids) > 1 else ids[0]]
        default_dur = 6 if scenario_id == "comm_failure" else (3 if scenario_id != "normal" else 0)
        self.active = ActiveScenario(scenario_id, targets, duration_ticks or default_dur, magnitude)
        self._system_alert(f"Scenario '{scenario_id}' injected on {', '.join(targets)}")

    def subscribe(self):
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q):
        self.subscribers.discard(q)

    async def _loop(self):
        try:
            while self.status != STOPPED:
                if self.status == RUNNING:
                    result = await self.tick()
                    for q in list(self.subscribers):
                        try:
                            q.put_nowait(result)
                        except asyncio.QueueFull:
                            pass
                await asyncio.sleep(self.tick_interval_s)
        except asyncio.CancelledError:
            pass

    # ---- fault programs: raw physics in, mutated physics (or None=gap) out ----
    def _apply(self, st: StationState, t: float, p: float, h: float):
        sc = self.active
        if sc is None or sc.scenario_id == "normal" or st.station_id not in sc.targets:
            return t, p, h
        sid = sc.scenario_id
        m = sc.magnitude
        if sid == "temp_spike":
            return t + 12.0 * m, p, h
        if sid == "temp_drop":
            return t - 12.0 * m, p, h
        if sid == "frozen":
            if "latched" not in sc.state:
                sc.state["latched"] = {}
            if st.station_id not in sc.state["latched"]:
                sc.state["latched"][st.station_id] = (t, p, h)
            return sc.state["latched"][st.station_id]
        if sid == "drift":
            k = sc.state.get(f"drift_{st.station_id}", 0.0) + 0.8 * m
            sc.state[f"drift_{st.station_id}"] = k
            return t + k, p, h
        if sid == "pressure":
            return t, p + 18.0 * m, h
        if sid == "humidity":
            return t, p, max(0.0, min(100.0, h - 35.0 * m))
        if sid in ("missing", "comm_failure"):
            return None
        if sid == "multivariate":
            return t + 6.0 * m, p, min(100.0, h + 25.0 * m)
        if sid in ("extreme_weather", "multi_station_event"):
            return t + 12.0 * m, p - 4.0 * m, max(0.0, h - 16.0 * m)
        if sid == "multi_failure":
            idx = sc.targets.index(st.station_id) % 3
            if idx == 0:
                if "latched" not in sc.state:
                    sc.state["latched"] = {}
                sc.state["latched"].setdefault(st.station_id, (t, p, h))
                return sc.state["latched"][st.station_id]
            if idx == 1:
                k = sc.state.get(f"drift_{st.station_id}", 0.0) + 0.8 * m
                sc.state[f"drift_{st.station_id}"] = k
                return t + k, p, h
            return t + 12.0 * m, p, h
        return t, p, h

    # ---- one real pipeline step ----
    async def tick(self) -> dict:
        async with self.session_factory() as session:
            # Live neighbour values first (this tick's physics for all stations)
            live: dict[str, tuple] = {}
            mutated: dict[str, tuple | None] = {}
            for sid, st in self.stations.items():
                climate = STATION_CLIMATE.get(sid, {"base_temp": 26.0, "base_hum": 60.0,
                                                    "season_amp": 4.0, "diurnal_amp": 4.5, "elev_m": 200.0})
                t, p, h = _clean_physics(climate, st.ts, st.rng, st.physics)
                mutated[sid] = self._apply(st, t, p, h)
                if mutated[sid] is not None:
                    live[sid] = mutated[sid]
            readings, detections = [], []
            for sid, st in self.stations.items():
                ts = st.ts
                val = mutated[sid]
                if val is None:
                    st.skip_streak += 1
                    readings.append({"station_id": sid, "timestamp": ts.isoformat(),
                                     "skipped": True, "skip_streak": st.skip_streak})
                    # Gap pipeline only on confirmed outage (streak 3): one real COMM row.
                    # Gaps are never stored, so the streak is reconstructed as a
                    # synthetic blank tail for the gate to count.
                    if st.skip_streak == 3:
                        history = await load_history(session, sid)
                        tail = [{"timestamp": ts - (st.skip_streak - k) * self.step,
                                 "temperature": None, "pressure": None, "humidity": None}
                                for k in range(st.skip_streak - 1)]
                        current = {"timestamp": ts, "temperature": None, "pressure": None, "humidity": None}
                        result = self.engine.detect(current, history + tail)
                        nb = [{"station_id": k, "temperature": v[0], "pressure": v[1], "humidity": v[2]}
                              for k, v in live.items()]
                        sh = await load_sensor_health(session, sid)
                        cls = classify_event(current, history, result, neighbors=nb, sensor_health=sh)
                        guard = guard_check(current, history, result, neighbors=nb, sensor_health=sh)
                        exp = build_explanation(current, history, result, cls, guard, neighbors=nb)
                        row = await persist_detection(session, sid, ts, result, cls, guard, exp)
                        alert = await raise_alert(session, sid, row.id, result.severity,
                                                  f"{sid}: {result.anomaly_type} score={result.anomaly_score}")
                        detections.append({"station_id": sid, "anomaly_type": result.anomaly_type,
                                           "anomaly_score": result.anomaly_score,
                                           "event_type": cls.event_type, "alert_id": alert.id})
                    st.ts = ts + self.step
                    continue
                st.skip_streak = 0
                t, p, h = (round(v, 2) for v in val)
                obs = Observation(station_id=sid, timestamp=ts, temperature=t, pressure=p, humidity=h)
                session.add(obs)
                await session.flush()
                history = await load_history(session, sid)
                # SQLite round-trips naive; exclude the just-inserted row.
                nts = ts.replace(tzinfo=None) if ts.tzinfo else ts
                history = [x for x in history if (x["timestamp"].replace(tzinfo=None)
                           if getattr(x["timestamp"], "tzinfo", None) else x["timestamp"]) != nts]
                current = {"timestamp": ts, "temperature": t, "pressure": p, "humidity": h}
                result = self.engine.detect(current, history)
                entry: dict = {"station_id": sid, "timestamp": ts.isoformat(), "temperature": t,
                               "pressure": p, "humidity": h, "anomaly_type": result.anomaly_type,
                               "anomaly_score": result.anomaly_score}
                if result.anomaly_type != "NORMAL":
                    nb = [{"station_id": k, "temperature": v[0], "pressure": v[1], "humidity": v[2]}
                          for k, v in live.items() if k != sid]
                    nh = {}
                    for k in live:
                        if k != sid:
                            hrows = await load_history(session, k)
                            nh[k] = [x for x in hrows if (x["timestamp"].replace(tzinfo=None)
                                     if getattr(x["timestamp"], "tzinfo", None) else x["timestamp"]) != nts]
                    sh = await load_sensor_health(session, sid)
                    cls = classify_event(current, history, result, neighbors=nb,
                                         sensor_health=sh, neighbor_histories=nh)
                    guard = guard_check(current, history, result, neighbors=nb, sensor_health=sh)
                    exp = build_explanation(current, history, result, cls, guard, neighbors=nb)
                    row = await persist_detection(session, sid, ts, result, cls, guard, exp, obs.id)
                    alert = await raise_alert(session, sid, row.id, result.severity,
                                              f"{sid}: {result.anomaly_type} score={result.anomaly_score}")
                    entry["event_type"] = cls.event_type
                    entry["alert_id"] = alert.id
                    detections.append(entry)
                readings.append(entry)
                await recompute_health(session, sid)
                st.ts = ts + self.step
            await session.commit()
            self.tick_count += 1
            if self.active and self.active.scenario_id != "normal":
                self.active.ticks_left -= 1
                if self.active.ticks_left <= 0:
                    self.active = None
            return {"type": "tick", "tick": self.tick_count, "status": self.status,
                    "scenario": self.active.scenario_id if self.active else None,
                    "readings": readings, "detections": detections}
