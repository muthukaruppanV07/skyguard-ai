# MissingLink AI

A community-sourced, AI-assisted platform for reporting missing persons and
submitting sighting leads — with a **human-in-the-loop** matching pipeline that
scores photo quality, face, clothing, location and time signals, explains every
ranked lead in plain English, and **never acts automatically**.

> **Demo notice** — everything in this repo runs on synthetic, seeded data.
> Real deployments require real model weights, real identity verification and
> human oversight of every AI suggestion.

---

## System overview

```
┌────────────┐   HTTPS    ┌──────────────┐  REST (X-AI-API-Key)   ┌───────────────────┐
│  Next.js   │ ─────────► │   Spring     │ ─────────────────────► │   FastAPI         │
│  frontend  │  (JWT)     │   Boot API   │    POST /v1/analyze    │   AI service      │
└────────────┘            └──────┬───────┘                        │  vision + ranking │
        (WS) realtime            │  └─────────────────────────────┴───────────────────┘
        ┌──────────┐             │  JPA / Flyway / pgvector
        │  Redis   │             ▼
        └──────────┘      ┌──────────────────┐
                         │  PostgreSQL +     │  (PostGIS, pgvector)
                         │  pgvector/pg16    │
                         └──────────────────┘
```

- **backend/springboot** — Spring Boot 3.3 / Java 21 REST API: JWT + RBAC
  security, cases, sightings, evidence (malware-scanned), geo search zones,
  notifications, full audit trail, admin reports.
- **ai-service** — FastAPI vision + matching pipeline: image quality, face
  detection, object/attribute extraction, 512-d embeddings (pgvector),
  weighted multi-signal ranking with explanations & limitations. Ships with a
  deterministic *fallback* embedder so the whole flow runs without GPU/model
  downloads; real CLIP/insightface/YOLO providers are wired as optional drops.
- **frontend** — Next.js 15 + TypeScript + Tailwind: public landing, sign in /
  register, missing-person report wizard, photo sighting submission, public map
  (Leaflet), role-aware dashboards, investigator match-review queue.
- **database** — Flyway migrations (schema) + synthetic seed data for a demo.

See `docs/` for deep dives:
[architecture](docs/architecture.md) · [API](docs/api.md) ·
[security](docs/security.md) · [database schema](docs/database-schema.md) ·
[AI model](docs/ai-model.md).

---

## Quick start (Docker Compose)

1. Copy the environment template and change the secrets:

   ```bash
   cp .env.example .env
   # at minimum change: POSTGRES_PASSWORD, JWT_SECRET, ENCRYPTION_KEY,
   #                    AI_SERVICE_API_KEY, SPRING_DATASOURCE_PASSWORD
   ```

2. Start everything:

   ```bash
   docker compose up -d --build
   ```

3. Open:
   - Frontend: http://localhost:3000
   - API: http://localhost:8080/api/v1
   - AI docs: http://localhost:8000/docs
   - Seed data is loaded automatically (Flyway `V3__seed_demo_data.sql`).

4. Seeded demo accounts:

   | Role         | Email                     | Password  |
   |--------------|---------------------------|-----------|
   | Admin        | `admin@missinglink.local` | `password`|
   | Investigator | `investigator@example.com`| `password`|

   Public sign-up is available on the frontend (or via `POST /auth/register`).

---

## End-to-end demo

`scripts/demo.sh` drives the whole flow via the API — register users, create a
public case, submit a sighting (optionally with a real photo), and read the
ranked investigator queue:

```bash
scripts/demo.sh                       # text-only sighting
scripts/demo.sh /path/to/photo.jpg    # include a photo (face/clothing signals)
```

Manual walk-through:

1. Register/sign in on the frontend → **Report a missing person**.
2. **Submit a sighting** with a photo and location (the browser can use
   geolocation).
3. Sign in as `investigator@example.com` → **Match queue** — each lead shows
   its score, which signals contributed, and the AI's stated limitations.
4. Accept / reject / escalate / mark duplicate. Every action is audited.

---

## Local development (without Docker)

| Component    | How to run                                                                 |
|--------------|----------------------------------------------------------------------------|
| Database     | `docker compose up -d postgres redis`                                       |
| Backend      | `cd backend/springboot && mvn spring-boot:run` (JDK 21, Maven 3.9+)         |
| AI service   | `cd ai-service && python -m venv .venv && pip install -r requirements.txt && uvicorn app.main:app --port 8000` |
| Frontend     | `cd frontend && npm install && npm run dev`                                 |

> The backend intentionally starts without `ENCRYPTION_KEY` using an ephemeral
> dev key (warns loudly). **Production must set a real 64-hex-char key.**

---

## Tests & CI

- **Backend** — `cd backend/springboot && mvn verify` (JUnit 5 + AssertJ + Mockito).
- **AI service** — `cd ai-service && pytest -q` (10 tests, no DB/GPU required).
- **Frontend** — `cd frontend && npx tsc --noEmit && npm run build`.

GitHub Actions (`.github/workflows/ci.yml`) runs all three on push/PR.

---

## Security notes

- JWT access tokens (15 min) + rotating refresh tokens (7 days), BCrypt password
  hashes, role/permission-based authorization (`@PreAuthorize`).
- Uploads are validated by magic bytes and scanned for embedded scripts;
  evidence is stored outside the public webroot and served only via expiring
  HMAC-signed URLs.
- PII/identifying fields are encrypted at rest (AES-256-GCM).
- Every security-relevant action is written to the audit log.
- AI results are never authoritative: each match lists its limitations and
  requires a human decision.

See [docs/security.md](docs/security.md) for the full threat model.

---

## Repository layout

```
missinglink-ai/
├── backend/springboot/     # Spring Boot API + Flyway migrations + tests
├── ai-service/             # FastAPI vision/matching pipeline + tests
├── frontend/               # Next.js app
├── database/               # postgis init for the pgvector image
├── docs/                   # architecture, api, security, schema, ai-model
├── infrastructure/docker/  # Dockerfiles (root-context)
├── scripts/demo.sh         # end-to-end API demo
├── docker-compose.yml
└── .github/workflows/ci.yml
```
