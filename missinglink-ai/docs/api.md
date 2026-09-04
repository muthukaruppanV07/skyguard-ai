# MISSINGLINK AI — API Reference

Base URL: `http://localhost:8080/api/v1`
Auth: `Authorization: Bearer <access_token>`
Docs: OpenAPI at `/api/v3/api-docs`, Swagger UI at `/swagger-ui.html`
Versioning: `/api/v1/*` (path-versioned).

All payloads JSON (except `multipart/form-data` for uploads). Errors use:

```json
{ "timestamp": "...", "status": 400, "error": "Validation failed",
  "path": "/api/v1/cases", "fieldErrors": { "age": "must be 0-120" } }
```

---

## Auth
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | register (default PUBLIC_USER) |
| POST | `/auth/login` | public | login → access+refresh |
| POST | `/auth/refresh` | public | rotate refresh token |
| POST | `/auth/logout` | any | revoke refresh token |
| GET | `/auth/me` | any | current profile + permissions |
| POST | `/auth/change-password` | any | change own password |

## Cases
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/cases` | PUBLIC_USER/FAMILY | create case (wizard step payloads) |
| GET | `/cases` | any+public flag | list/search cases |
| GET | `/cases/{id}` | case-authorized | detail |
| PATCH | `/cases/{id}` | FAMILY/INVESTIGATOR | update |
| POST | `/cases/{id}/photos` | FAMILY | upload authorized photo |
| POST | `/cases/{id}/profile/generate` | FAMILY | trigger AI profile generation |
| POST | `/cases/{id}/timeline` | INVESTIGATOR | append event |
| PATCH | `/cases/{id}/status` | INVESTIGATOR/ADMIN | change status |
| DELETE | `/cases/{id}` | ADMIN | soft-delete + retention workflow |
| GET | `/cases/public` | public | only `is_public=true`, no sensitive fields |

## Sightings
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/sightings` | public/any | submit sighting (multipart) |
| GET | `/sightings/{id}` | case-authorized | detail |
| GET | `/sightings` | INVESTIGATOR | list w/ filters |
| PATCH | `/sightings/{id}/status` | INVESTIGATOR | verify/reject/duplicate |
| GET | `/sightings/clusters` | INVESTIGATOR | evidence clusters |

## Evidence
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/evidence` | any | upload evidence file (validated) |
| GET | `/evidence/{id}` | case-authorized | metadata |
| GET | `/evidence/{id}/url` | case-authorized | **signed** download URL (audited) |
| GET | `/evidence/{id}/analysis` | case-authorized | AI analysis summary |

## Matches
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/matches` | INVESTIGATOR | queue (sort: relevance/recent/geo/quality) |
| GET | `/matches/{id}` | INVESTIGATOR | detail + explanation + limitations |
| PATCH | `/matches/{id}/decision` | INVESTIGATOR | accept/reject/more-info/duplicate/escalate |
| POST | `/matches/{id}/reanalyze` | INVESTIGATOR | re-run with newer model version |

## Geospatial
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/geo/cases/{caseId}/map` | case-authorized | markers (case, sightings, matches, zones) |
| POST | `/geo/cases/{caseId}/search-zones` | INVESTIGATOR | generate zones (AI-assisted) |
| GET | `/geo/cases/{caseId}/search-zones` | case-authorized | list zones |

## Notifications
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/notifications` | any | own in-app notifications |
| PATCH | `/notifications/{id}/read` | any | mark read |

## Search
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/search/cases` | any | full-text + filter + geo |
| GET | `/search/sightings` | INVESTIGATOR | sightings search |

## Admin
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/admin/users` | ADMIN | list users |
| PATCH | `/admin/users/{id}` | ADMIN | edit role/status |
| GET | `/admin/stats` | ADMIN | case/AI/storage stats |
| GET | `/admin/audit` | ADMIN | audit logs (paginated, filterable) |
| GET | `/admin/model-versions` | ADMIN | model registry + metrics |
| GET | `/admin/system-health` | ADMIN | service health |
| POST | `/admin/reports` | any | file abuse report |
| GET | `/admin/reports` | ADMIN | review abuse reports |

## AI Gateway (backend→AI, not public)
`POST /api/v1/ai/analyze-image` (multipart) — forwards to FastAPI `/analyze-image`
`POST /api/v1/ai/analyze-sighting` — forwards to `/analyze-sighting`

---

## Workflow contracts

### Potential match (response shape)
```json
{
  "id": 501,
  "caseReference": "MP-102",
  "sightingReference": "ST-1189",
  "overallScore": 0.84,
  "signals": {
    "face": 0.82, "clothing": 0.76, "accessory": 0.7, "body": 0.72,
    "image": 0.81, "location": 0.91, "time": 0.88, "text": 0.74
  },
  "status": "AWAITING_REVIEW",
  "warning": "POTENTIAL MATCH — HUMAN VERIFICATION REQUIRED",
  "explanation": ["High visual similarity", "Similar clothing", "Within configured geographic radius", "Time interval is relevant"],
  "limitations": ["Image quality is low", "Lighting differs", "Location information is uncertain"]
}
```

### Search zones (response shape)
```json
{ "zones": [
  { "zoneType": "HIGH_PRIORITY", "priority": 1, "radiusKm": 5.0,
    "geometry": {"type":"Polygon","coordinates":[...]},
    "rationale": "Within walk distance of last known location",
    "aiGenerated": true, "requiresReview": true }
]}
```

---

## Pagination / filtering / sorting
- Pagination: `?page=0&size=20` → `{ content, page, size, totalElements, totalPages }`
- Filtering: `?status=ACTIVE&priorityLevel=CRITICAL`
- Sorting: `?sort=overallScore,desc`
