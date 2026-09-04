# MISSINGLINK AI — System Architecture

> Intelligent Missing Person Search, Sighting Verification & Geospatial Intelligence Platform.
> **Assistance & lead-generation system — never an autonomous identity-verification system.**

---

## 1. Guiding principles

1. **Human-in-the-loop.** Every AI output is a *potential match* that requires authorized
   human verification. The UI never says "IDENTITY CONFIRMED" — only
   `POTENTIAL MATCH — HUMAN VERIFICATION REQUIRED`.
2. **Privacy by design.** Data minimization, configurable retention, encryption at rest,
   signed URLs, consent records, and role-based access.
3. **No black boxes.** Every suggested lead ships with an explanation panel (`why`) and
   explicit `limitations`.
4. **Replaceable internals.** External services (face model, CLIP, storage, email, SMS)
   are behind provider interfaces so a demo provider can be swapped for the real thing.
5. **Synthetic demo data only.** No real people's private information is ever used.

---

## 2. High-level topology

```
                    ┌─────────────────────────────┐
                    │  Frontend (Next.js/TS)      │
                    │  Landing · Wizard · Console │
                    └──────────────┬──────────────┘
                                   │ REST (JWT) + STOMP/WebSocket
                    ┌──────────────▼──────────────┐
                    │  Backend (Spring Boot)      │
                    │  Auth · Cases · Sightings   │
                    │  Evidence · Matches · Geo   │
                    │  Notifications · Audit      │
                    │  AI Gateway (secure proxy)  │
                    └───────┬──────────────┬──────┘
                            │ HTTPS w/ key │
             ┌──────────────▼───┐   ┌──────▼────────────────┐
             │ AI Service       │   │ PostgreSQL (+pgvector│
             │ (FastAPI/GPU)    │   │ +PostGIS) + Redis    │
             │ vision pipeline  │   │                      │
             └──────────────────┘   └──────────────────────┘
```

- **Frontend →** Next.js App Router, TypeScript, Tailwind. Talks only to the backend.
- **Backend →** Spring Boot 3, the single API surface. Owns RBAC, workflows, audit, and
  the **AI Gateway** that forwards only validated analysis requests to the AI service.
- **AI Service →** FastAPI. Face detection/embedding, object/clothing detection, CLIP
  embeddings, vector search (pgvector), multi-modal ranking, explanations.
- **Data →** PostgreSQL with `pgvector` (embeddings) and `PostGIS` (geo); Redis for
  rate limiting / pub-sub fan-out of realtime events.

### Why an AI Gateway in the backend?
The AI service never talks to the browser. The backend enforces authorization,
writes audit records, and forwards only validated media references. This keeps the AI
surface small and prevents bypassing RBAC. API key is server-side only.

---

## 3. Backend module map

| Module | Package | Responsibility |
|---|---|---|
| Authentication Service | `security` | JWT issue/refresh/revoke, MFA-ready, session, consent login |
| User Service | `user` | users, roles, permissions, orgs, RBAC enforcement |
| Case Service | `case` | missing-person case lifecycle, wizard steps, profile generation, classification |
| Evidence Service | `evidence` | upload validation, checksum, malware-scan hook, storage, signed URLs |
| Sighting Service | `sighting` | sighting intake, dedup/clustering, metadata stripping |
| Matching Service | `matching` | potential matches, verification workflow, explanation panel |
| Notification Service | `notification` | in-app + email (console/smtp) + SMS/WhatsApp interface |
| Geospatial Service | `geospatial` | PostGIS queries, search zones, lead clusters |
| Audit Service | `audit` | append-only audit trail of all sensitive actions |
| AI Gateway | `aigateway` | thin, authenticated HTTP client to FastAPI |
| Admin | `admin` | user mgmt, stats, model versions, abuse reports, system health |
| Search | `search` | full-text + filter + vector + geo combined queries |
| Storage | `storage` | provider interface: `local` and `s3` (mock), signed URLs |

---

## 4. Request flow examples

### 4.1 Report a missing person
```
Frontend wizard → POST /api/v1/cases (JWT, role public/family)
  → CaseService validates, builds CaseSummary
  → uploads authorized photos → EvidenceService (malware check, checksum)
  → AI Gateway: POST /analyze-image (per photo) → face/clothing/object embeddings
  → embeddings upserted to evidence_embeddings (pgvector)
  → ProfileGeneration → person_profiles.searchable_text + embedding
  → audit_logs.insert + notifications (in-app/email)
  → returns case_reference (e.g. MP-102)
```

### 4.2 Report a sighting
```
POST /api/v1/sightings
  → validate file, scan (clamav hook / provider), quality gate
  → strip EXIF from public copies
  → dedup check (checksum + perceptual hash + cluster logic)
  → AI Gateway: /analyze-sighting → embedding + potential matches
  → PotentialMatch rows created (status=AWAITING_REVIEW)
  → realtime: WS push to investigators; notifications
```

### 4.3 Investigator verification
```
PATCH /api/v1/matches/{id}/decision  (role INVESTIGATOR/AUTHORITY)
  → decision (ACCEPT/REJECT/MORE_INFO/DUPLICATE/ESCALATE)
  → verification_records.insert + case_timeline.append + audit
  → if ACCEPT → sighting marked VERIFIED, geo intelligence refreshed
```

---

## 5. AI pipeline

See [`ai-model.md`](./ai-model.md) for the full model description. Summary:

```
IMAGE → quality gate → face detect → face embedding
     → person/clothing detect → object detect → visual features
     → vector search (pgvector, cosine)
     → multi-modal rank (face + clothing + accessory + location + time + text)
     → explanation + limitations → human review queue
```

Scoring is intentionally **multi-modal**, never face-only:

```
overall = w_face·face_sim + w_clothing·clothing_sim + w_accessory·accessory_sim
        + w_body·body_sim + w_img·image_sim + w_loc·location_rel + w_time·time_rel
        + w_text·text_sim
```

---

## 6. Realtime

- STOMP over WebSocket at `/ws`.
- Backend publishes to `/topic/case.{caseId}` and `/queue/user.{userId}` on:
  new sightings, match creation, verification decisions, case status changes,
  notifications, map marker updates.

---

## 7. Security decisions (summary)

| Concern | Decision |
|---|---|
| AuthN | JWT access (15 min) + rotating refresh token (7 d), BCrypt hashes |
| AuthZ | RBAC, 3-level: roles → permissions → endpoint guards; case-level data access via `CaseAccessService` |
| Transport | All external: TLS; service-to-service: HTTP + `AI_SERVICE_API_KEY` header |
| Data at rest | AES-256 field encryption for sensitive text; app-level crypto service |
| Secrets | `.env` only; never in source; CI uses GitHub secrets |
| Uploads | size/type allowlist, checksum, malware-scan provider hook, virus-flag workflow |
| Abuse | rate limiting (bucket/Redis), CAPTCHA-ready field, abuse reports, duplicate detection |
| Audit | append-only `audit_logs` for every sensitive mutation incl. IP/user-agent |
| Retention | configurable `DATA_RETENTION_DAYS`, case deletion workflow (soft delete) |

Full details in [`security.md`](./security.md).

---

## 8. Deployment

- `docker-compose.yml` orchestrates postgres+postgis, redis, backend, ai-service, frontend.
- GPU: set `AI_FALLBACK_ALLOWED=false` and mount GPU for the ai-service container.
- CI/CD: `.github/workflows/ci.yml` (lint, tests, build, push) + `cd.yml` (deploy).
- See [`../README.md`](../README.md#deployment) and `infrastructure/deployment/`.

---

## 9. Scalability plan

1. **Stateless backend** (JWT) → horizontal scale behind LB.
2. **Redis** for rate limits + pub/sub → replaces in-memory buckets.
3. **Object storage** (S3) for evidence files.
4. **GPU pool** for the AI service; model warm pools + queue.
5. **Sharded pgvector** / external vector DB (Qdrant) when index size grows.
6. **Elasticsearch** for cross-entity search.
7. **Worker queue** (SQS/RabbitMQ) for long-running analysis + notification fan-out.
8. **Observability** OpenTelemetry → Prometheus/Grafana; AI drift monitoring.
