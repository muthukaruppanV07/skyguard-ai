# MISSINGLINK AI — Security Architecture

## 1. Threat model (top risks)

| Risk | Mitigation |
|---|---|
| Unauthorized case access | RBAC + per-case authorization (`CaseAccessService`) |
| Token theft | Short-lived JWT (15 min) + rotating refresh tokens (hashed at rest, revocable) |
| Uploaded malware | File allowlist (types/size), magic-byte sniff, SHA-256, malware-scan provider hook (e.g. ClamAV) |
| Abuse / spam | Rate limiting, CAPTCHA-ready field, duplicate detection, abuse reports |
| PII leakage in logs | Redaction of sensitive fields in `audit_logs.details` |
| Vector/geo inference | Public map endpoints blur/aggregate exact locations; signed URLs expire |
| Prompt injection via sighting text | Sightings text is treated as data, never concatenated into SQL/instructions |
| Secret exposure | `.env` only; service-to-service calls use `AI_SERVICE_API_KEY`; CI uses GitHub secrets |

## 2. Authentication

- Passwords hashed with **BCrypt** (strength 12).
- **JWT access token** (`HS256`, secret from env, ≥64 chars): subject=user id, claims:
  `uid, role, perms[]`, exp 15 min.
- **Refresh token**: 128-bit random, stored hashed (SHA-256) in `refresh_tokens`,
  rotation on every use, revocation on logout/compromise, 7-day TTL.
- **MFA-ready**: `users.mfa_enabled`, `otp_secret` (encrypted). A `MfaChallenge` hook
  exists so TOTP can be switched on with one flag (`MFA_REQUIRED`).

## 3. Authorization (RBAC)

- Roles: `PUBLIC_USER`, `FAMILY`, `INVESTIGATOR`, `ADMIN`.
- Permissions map: `case:read`, `case:write`, `case:status`, `sighting:read`,
  `sighting:review`, `match:review`, `evidence:read`, `evidence:upload`,
  `admin:manage`, `audit:read`, `geo:write`, etc.
- Method security: `@PreAuthorize("hasAuthority('match:review')")`.
- **Case-level access** (beyond role): reporter/family of the case, org members,
  investigators, admins. `CaseAccessService.canAccess(user, caseId)`.

## 4. Data protection

- **At rest**: sensitive text (identification marks, notes, phone numbers) encrypted
  with AES-256/GCM via `CryptoService` (key from env, 64 hex chars).
- **Files**: stored under `storage_root`, filenames are random UUIDs; EXIF stripped on
  public copies; SHA-256 integrity; access via **signed URLs** (HMAC, expiry).
- **In transit**: TLS in production (terminated at LB/proxy); service-to-service uses
  `https://` + API key header.

## 5. Upload & evidence pipeline

```
client → POST /evidence (multipart)
  → size check (≤25 MB) → content-type allowlist (jpg/png/webp/mp4/mov/pdf)
  → magic-byte validation (no trusting the browser header)
  → SHA-256 checksum → malware scan (provider hook, default "pass-through")
  → EXIF strip for public copies → store → AI analysis (async)
  → audit_logs: evidence:upload, evidence:access, evidence:download
```

## 6. Rate limiting

- Bucket-based limiter keyed by `(ip, userId?, endpoint group)`.
- Default 60 req/min; stricter on `/auth/login` (5/min) and `/sightings` (10/min).
- Swappable Redis-backed implementation (interface `RateLimiter`).

## 7. Audit trail

- Every sensitive mutation calls `AuditService.record(...)`.
- Fields: actor, action, resourceType, resourceId, ip, userAgent, details (redacted),
  timestamp. Never overwritten.
- Admin UI reads audit logs; retention applies after legal minimum.

## 8. Privacy / consent

- `consent_records` for photo usage and case visibility.
- `is_public` toggles whether a case appears in public search (without PII).
- Public map endpoints never reveal exact coordinates of the missing person's
  last-known location when it would create safety risk (return aggregated/blurred markers).
- Retention: `DATA_RETENTION_DAYS`; admin delete → soft delete → purge job.

## 9. Secrets handling checklist
- [ ] Copy `.env.example` → `.env`
- [ ] Rotate `JWT_SECRET`, `ENCRYPTION_KEY`, `AI_SERVICE_API_KEY`
- [ ] Never commit `.env`; `.gitignore` blocks it
- [ ] Use GitHub Secrets for CI/CD
- [ ] Restrict DB/user credentials; separate read-only account for reporting if needed
