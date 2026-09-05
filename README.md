# SKYGUARD AI

**AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (AWS)**

> "From Raw Weather Data to Trusted Weather Intelligence."

---

## Problem Statement

**SIH 2026 | Problem Statement ID: 26073**

**Organization:** Ministry of Earth Sciences (MoES)  
**Department:** India Meteorological Department (IMD)  
**Category:** Software  
**Theme:** Disaster Management

Automatic Weather Stations continuously measure temperature, atmospheric pressure, and relative humidity. Traditional threshold-based quality control is insufficient for detecting complex temporal and multivariate anomalies caused by sensor malfunctions, calibration drift, frozen sensors, communication failures, and environmental interference.

---

## Solution

**SKYGUARD AI** is a hybrid, explainable, and self-aware AWS quality-control platform that combines:

1. **Rule-Based QC** - Deterministic validation checks
2. **Isolation Forest** - Unsupervised anomaly detection
3. **Autoencoder** - Deep reconstruction-based detection
4. **Temporal Analysis** - Rate-of-change, drift, persistence detection
5. **Multivariate Consistency** - Physical relationship validation (T-H-P)
6. **Spatial Consistency** - Neighboring station cross-validation

**Output:** Unified anomaly score (0-100), root cause classification, confidence scoring, explainable AI, sensor health monitoring, and corrected value estimation.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  SIMULATOR  │────▶│  INGESTION  │────▶│  VALIDATOR  │────▶│ FEATURE ENG │
│  (8 AWS)    │     │  (1Hz)      │     │  (Rules)    │     │  (30+ feat) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                     │
                                                                     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DASHBOARD  │◀────│  WEBSOCKET  │◀────│  FUSION     │◀────│  ML MODELS  │
│  (React)    │     │  (/ws/live) │     │  (0-100)    │     │  (IF + AE)  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           ▲                    │
                           │                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  REST API   │     │ ROOT CAUSE  │
                    │  (FastAPI)  │     │  CLASSIFIER │
                    └─────────────┘     └─────────────┘
                           │                    │
                    ┌──────┴──────┐     ┌──────┴──────┐
                    ▼             ▼     ▼             ▼
             ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
             │ EXPLAINER │ │  HEALTH   │ │ CORRECTION│ │  ALERTS   │
             │ (SHAP+txt)│ │  (0-100)  │ │ (Expected)│ │           │
             └───────────┘ └───────────┘ └───────────┘ └───────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| **ML** | Scikit-learn (Isolation Forest), PyTorch (Autoencoder), SHAP |
| **Database** | SQLite (MVP) → PostgreSQL/TimescaleDB (Production) |
| **Real-time** | FastAPI WebSocket |
| **Frontend** | React 18, Vite, Recharts, Leaflet, Tailwind CSS |
| **Simulation** | Custom AWS simulator with realistic meteorological patterns |

---

## Project Structure

```
skyguard-ai/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # All settings & weights
│   ├── api/                    # REST routes + WebSocket
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response
│   ├── services/               # Business logic orchestrators
│   ├── anomaly/                # Detection engines (6 modules)
│   ├── preprocessing/          # Validation + Feature engineering
│   ├── explainability/         # SHAP + Text explanations
│   ├── simulation/             # AWS simulator + Fault injection
│   ├── database/               # Session, repos, init
│   └── utils/                  # Helpers
├── frontend/
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Route pages
│   │   ├── services/           # API + WebSocket clients
│   │   ├── charts/             # Chart utilities
│   │   └── utils/              # Formatters, constants
├── data/                       # Raw, processed, synthetic data
├── models/                     # Trained model artifacts
├── tests/                      # Unit + Integration tests
├── docs/                       # Documentation
├── scripts/                    # Training, evaluation, demo scripts
├── requirements.txt
├── package.json
└── docker-compose.yml
```

---

## Installation

### Backend

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m backend.database.init_db

# Run backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, proxied to backend at `http://localhost:8000`.

---

## Running the Demo

```bash
# Terminal 1: Backend
uvicorn backend.main:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Demo scenario (optional)
python scripts/run_demo.py
```

Open `http://localhost:5173` and use the **Demo Controls** panel to inject anomalies:
- Inject Temperature Spike
- Inject Sensor Drift
- Freeze Sensor
- Communication Failure
- Multivariate Anomaly
- Reset Demo

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stations` | List all stations |
| GET | `/api/stations/{id}` | Station details |
| GET | `/api/readings` | Paginated readings |
| GET | `/api/anomalies` | Paginated anomalies |
| GET | `/api/anomalies/{id}` | Anomaly details |
| GET | `/api/health` | Network health summary |
| GET | `/api/health/{id}` | Station sensor health |
| GET | `/api/statistics` | Dashboard statistics |
| POST | `/api/detect` | Manual detection trigger |
| POST | `/api/simulate/anomaly` | Inject anomaly |
| POST | `/api/simulate/reset` | Reset simulator |
| GET | `/api/explanation/{id}` | Detailed explanation |
| GET | `/api/models` | Model info & metrics |
| WS | `/ws/live` | Real-time updates |

---

## Anomaly Types Detected

| Type | Description |
|------|-------------|
| TEMPERATURE_SPIKE | Sudden temperature jump |
| PRESSURE_SPIKE | Sudden pressure jump |
| HUMIDITY_SPIKE | Sudden humidity jump |
| SENSOR_DRIFT | Gradual calibration drift |
| FROZEN_SENSOR | Stuck/constant readings |
| MISSING_DATA | Data gaps |
| DUPLICATE_DATA | Repeated timestamps |
| COMMUNICATION_FAILURE | Transmission issues |
| MULTIVARIATE_INCONSISTENCY | T-H-P relationship violation |
| POSSIBLE_SENSOR_MALFUNCTION | Likely sensor fault |
| POSSIBLE_REAL_WEATHER_EVENT | Genuine extreme weather |

---

## Severity Levels

| Score Range | Level | Color |
|-------------|-------|-------|
| 0-30 | NORMAL | 🟢 Green |
| 30-50 | LOW | 🟢 Light Green |
| 50-70 | SUSPICIOUS | 🟡 Yellow |
| 70-85 | HIGH | 🟠 Orange |
| 85-100 | CRITICAL | 🔴 Red |

---

## Key Innovation: Hybrid Fusion Scoring

```
FINAL_SCORE = 
  0.15 × Rule_Score +
  0.25 × IF_Score +
  0.25 × AE_Score +
  0.15 × Temporal_Score +
  0.10 × Multivariate_Score +
  0.10 × Spatial_Score
```

All weights configurable in `config.py`.

---

## Explainability

Every anomaly includes:
- **SHAP values** for feature attribution
- **Human-readable explanation** (e.g., "Temperature increased from 31.5°C to 55.2°C within 15 minutes. This is significantly outside the station's learned temporal behavior. Nearby stations remain within normal range and the temperature-humidity relationship is inconsistent. The system assigns 96% probability to a temperature sensor anomaly.")
- **Contributing factors** breakdown
- **Confidence score** (0-1)

---

## Sensor Health Monitoring

Per-station, per-sensor health score (0-100) based on:
- Anomaly frequency & severity
- Drift detection
- Frozen reading count
- Missing data frequency
- Communication failures
- Autoencoder reconstruction error

**Status:** HEALTHY (≥80) → WARNING (60-79) → MAINTENANCE_RECOMMENDED (40-59) → CRITICAL (<40)

---

## Corrected Value Estimation

When anomaly detected:
- **Observed:** Raw sensor value
- **Expected:** AI-estimated true value (from temporal/spatial/multivariate models)
- **Correction Confidence:** Reliability of estimate
- **Raw data NEVER overwritten** - stored separately with full audit trail

---

## Model Evaluation

Run evaluation suite:
```bash
python scripts/evaluate_models.py
```

Compares:
- Baseline Rule-Based QC
- Isolation Forest
- Autoencoder
- Hybrid SkyGuard

Metrics: Accuracy, Precision, Recall, F1, FPR, FNR, Detection Latency
Per anomaly type: Spike, Drift, Frozen, Missing, Comm Failure, Multivariate

---

## Documentation

- `docs/SYSTEM_DESIGN.md` - Architecture details
- `docs/ML_METHODOLOGY.md` - ML pipeline & models
- `docs/API_DOCUMENTATION.md` - OpenAPI specs
- `docs/DEMO_GUIDE.md` - SIH demo walkthrough
- `docs/USE_CASES.md` - Operational scenarios

---

## Limitations

- Synthetic data only (no real IMD data in prototype)
- 8 simulated stations (not full IMD network)
- Models trained on synthetic patterns
- No historical model retraining pipeline (MVP)
- SQLite not suitable for production scale

---

## Future Scope

- Integration with real IMD AWS data feeds
- TimescaleDB for time-series optimization
- ONNX export for edge deployment (ESP32/Raspberry Pi)
- Federated learning across stations
- Advanced LSTM-AE for temporal sequences
- Automated model retraining pipeline
- Mobile app for field technicians
- Integration with IMD alerting systems

---

## License

Prototype for Smart India Hackathon 2024.  
Team: SKYGUARD AI

---

## Contact

**Problem Statement:** 26073  
**Organization:** Ministry of Earth Sciences (MoES)  
**Department:** India Meteorological Department (IMD)