# SKYGUARD AI — Final Dossier (SIH 26073 · MoES/IMD)

## 30-second pitch
IMD's Automatic Weather Stations stream temperature, pressure and humidity — but a strange reading is **not**
automatically a broken sensor. SkyGuard AI watches every reading with 9 fused detectors, compares it against
time, physics and neighbouring stations, and answers in plain language: **sensor fault or real weather — with
evidence, confidence and a recommended action.** Detect. Explain. Protect.

## Final feature list
- Real-time ingestion (REST + WebSocket streaming, 8-station simulator with 13 fault scenarios)
- Hybrid anomaly detection (9 detectors, 0–100 fused score, severity + confidence)
- Weather-vs-sensor classification (spatial/temporal/multivariate consistency + sensor health + ML score)
- False-alarm guard (6 checks, suppress recommendation)
- Explainable AI (why-flagged narrative, evidence, feature contributions, detector trail)
- Spatial intelligence (neighbour agreement, °C deviation, regional consistency bands)
- Sensor health 0–100 (8 counted penalty factors, 14-day trend)
- Predictive maintenance (6 degradation signals → risk/priority/reason/actions, work orders)
- Alert center (CRITICAL/HIGH/MEDIUM/LOW/INFO/SYSTEM, acknowledge/mute/resolve, live feed)
- Data quality center (5 dimensions, 8 issue types, 4 filters)
- Model evaluation (threshold baseline vs hybrid on 9 labeled categories)
- Reports (5 types: preview/generate/persist/export JSON+CSV)
- Dashboards: command center, live monitor, stations, station intelligence, analytics, judge mode,
  presentation mode, 5-minute demo mode, Why-SkyGuard page

## Final architecture
```
AWS stations / simulator → FastAPI ingest → SQLite
  → feature engineering (56 T/P/H + time features)
  → 9 detectors → weighted fusion (0–100) → classification → guard → explanation
  → anomaly rows → alerts → health recompute → maintenance intel
  → React 18 + TypeScript command center (Recharts, Leaflet, WebSocket live)
```

## ML methods used
Physical validation, rolling statistical z-score, robust MAD z-score, rate-of-change,
IsolationForest (per-decision fit on trailing history ≥50, sklearn), temporal analysis,
multivariate T–H–P coupling, frozen-streak, drift slope; weighted fusion; spatial z-score
vs neighbours; rule-based false-alarm guard. No deep nets at inference; no SHAP (documented:
exact fusion decomposition is faithful by construction).

## Evaluation results (default config, seed 42, 18 episodes, measured live)
- Threshold: acc 0.792, prec 0.873, rec 0.633, F1 0.734, FPR 0.076
- Hybrid: acc 0.778, prec 1.000, rec 0.510, F1 0.676, FPR 0.000
- Latency: threshold 0.14 steps (14/16 episodes), hybrid 1.4 steps (15/16)
- Reading: hybrid trades recall for **zero false alarms** (precision 1.0) — the operator-trust
  tradeoff; threshold catches more, cries wolf 9× more. Per-category: spike/multivariate/missing
  strong; gradual drift weak per-step (documented limitation).

## Test results
- Backend: 161 passed (`pytest tests/ -q`)
- Frontend: `tsc --noEmit` clean, `vite build` succeeds
- Live sweeps: 30+ endpoints incl. error paths; WS streaming verified; demo story verified end-to-end

## Limitations (stated openly)
- Synthetic/simulated data; 8 stations, not the IMD fleet; SQLite dev DB
- Cold start (<~6 history points) can emit marginal 50–55 flags
- Gradual drift is hard per-step; post-spike recovery transient can echo-flag
- IF needs ≥50 history rows; short histories run statistical-only
- No online retraining loop; no edge deployment yet

## 5-minute demo script
- 00:00 INTRO — title + tagline
- 00:30 NETWORK — reset sim, warmup ticks, live health map
- 01:15 ANOMALY — inject ~55 °C spike on live-picked station, tick until flagged
- 02:00 INVESTIGATION — score, confidence, methods, why-narrative, neighbour table
- 03:00 VERDICT — isolated fault verdict, then multi-station event → weather verdict
- 04:00 HEALTH — live penalties, synced maintenance order (or honest no-order statement)
- 04:30 SUMMARY — capability checklist from real run data + "Detect. Explain. Protect."
- Run from `/demo` (START DEMO, AUTO PLAY) or presentation mode for recording.

## Likely judge questions + answers
1. **"Why not just thresholds?"** — Evaluation page: threshold FPR 0.076 vs hybrid 0.000; thresholds can't separate fault from weather (no spatial/multivariate context) and can't explain.
2. **"How do you tell sensor fault from real weather?"** — Three consistencies (spatial/temporal/multivariate) + health + ML score fused to probabilities; isolated 23σ spike → fault; shared coherent burst → weather. Both directions demoed live.
3. **"What about false alarms?"** — 6-check guard with suppress recommendation; measured FPR 0.0 on eval; cold-start marginals documented.
4. **"Explain a flag right now."** — Anomaly Center → any row → stored why + live reconstruction.
5. **"Does it work in real time?"** — WebSocket ticks run the full pipeline per station per tick; detection latency ~260 ms measured live (Judge mode).
6. **"Scale to 1000 stations?"** — Stateless FastAPI + per-station independent pipeline; SQLite→Postgres path; current measured headroom in Judge mode.
7. **"Where does 55 °C go if the limit is 50?"** — Sim writes raw truth; API input validation still rejects out-of-range manual posts (422); reads never hide stored anomalies.
8. **"Why is drift recall low?"** — Per-step detection of slow ramps is intrinsically hard; drift detector needs sustained slope; stated as limitation with the trend-based maintenance net catching it over days.
