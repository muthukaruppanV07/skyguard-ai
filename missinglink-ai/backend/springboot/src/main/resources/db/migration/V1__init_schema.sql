-- ============================================================
-- MISSINGLINK AI — Schema migration V1
-- Requires: postgresql + pgvector + postgis
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- Organizations
-- ------------------------------------------------------------
CREATE TABLE organizations (
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(255) NOT NULL UNIQUE,
    type           VARCHAR(50)  NOT NULL DEFAULT 'PRIVATE',   -- LAW_ENFORCEMENT|NGO|PRIVATE|FAMILY
    contact_email  VARCHAR(255),
    status         VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Roles & permissions (RBAC)
-- ------------------------------------------------------------
CREATE TABLE roles (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,    -- PUBLIC_USER|FAMILY|INVESTIGATOR|ADMIN
    description VARCHAR(255)
);

CREATE TABLE permissions (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE role_permissions (
    role_id       BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- ------------------------------------------------------------
-- Users
-- ------------------------------------------------------------
CREATE TABLE users (
    id             BIGSERIAL PRIMARY KEY,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    full_name      VARCHAR(255) NOT NULL,
    phone          VARCHAR(40),
    role_id        BIGINT NOT NULL REFERENCES roles(id),
    organization_id BIGINT REFERENCES organizations(id),
    status         VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',      -- ACTIVE|LOCKED|PENDING_VERIFICATION
    mfa_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    otp_secret_enc VARCHAR(255),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users (lower(email));
CREATE INDEX idx_users_role ON users (role_id);

-- ------------------------------------------------------------
-- Refresh tokens (rotated, hashed at rest)
-- ------------------------------------------------------------
CREATE TABLE refresh_tokens (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id, revoked);

-- ------------------------------------------------------------
-- Missing person cases
-- ------------------------------------------------------------
CREATE TABLE missing_person_cases (
    id                        BIGSERIAL PRIMARY KEY,
    case_reference            VARCHAR(20) NOT NULL UNIQUE,     -- e.g. MP-102
    reporter_id               BIGINT NOT NULL REFERENCES users(id),
    status                    VARCHAR(30) NOT NULL DEFAULT 'OPEN',  -- OPEN|ACTIVE|LOCATED|CLOSED|ARCHIVED
    priority_level            VARCHAR(20) NOT NULL DEFAULT 'STANDARD', -- STANDARD|HIGH|CRITICAL
    emergency_classification  VARCHAR(60),                     -- configurable label (never medical/legal)
    title                     VARCHAR(255),
    first_name                VARCHAR(120),
    last_name                 VARCHAR(120),
    age                       INT,
    gender                    VARCHAR(30),
    height_cm                 INT,
    identification_marks      TEXT,
    languages                 VARCHAR(500),
    last_known_activity       TEXT,
    transportation            VARCHAR(300),
    possible_destinations     VARCHAR(500),
    description               TEXT,
    last_known_place          VARCHAR(255),
    last_known_at             TIMESTAMPTZ,
    last_known_lat            DOUBLE PRECISION,
    last_known_lng            DOUBLE PRECISION,
    is_public                 BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at               TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                TIMESTAMPTZ
);
CREATE INDEX idx_cases_reporter ON missing_person_cases (reporter_id);
CREATE INDEX idx_cases_status   ON missing_person_cases (status, priority_level);
CREATE INDEX idx_cases_created  ON missing_person_cases (created_at DESC);
CREATE INDEX idx_cases_geo      ON missing_person_cases (last_known_lat, last_known_lng);

-- ------------------------------------------------------------
-- Consent records (authorization for photos/visibility)
-- ------------------------------------------------------------
CREATE TABLE consent_records (
    id            BIGSERIAL PRIMARY KEY,
    case_id       BIGINT NOT NULL REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    granter_id    BIGINT NOT NULL REFERENCES users(id),
    consent_type  VARCHAR(40) NOT NULL,          -- PHOTO_USE|CASE_VISIBILITY|PUBLIC_SEARCH
    consent_text  TEXT,
    signed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    storage_key   VARCHAR(500)
);
CREATE INDEX idx_consent_case ON consent_records (case_id);

-- ------------------------------------------------------------
-- Authorized photos
-- ------------------------------------------------------------
CREATE TABLE authorized_photos (
    id                 BIGSERIAL PRIMARY KEY,
    case_id            BIGINT NOT NULL REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    uploader_id        BIGINT NOT NULL REFERENCES users(id),
    storage_key        VARCHAR(500) NOT NULL,
    photo_type         VARCHAR(30) NOT NULL DEFAULT 'FRONT_FACE', -- FRONT_FACE|SIDE_PROFILE|FULL_BODY|OLDER
    consent_record_id  BIGINT REFERENCES consent_records(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_photos_case ON authorized_photos (case_id);

-- ------------------------------------------------------------
-- Person profiles (AI-generated searchable profile)
-- ------------------------------------------------------------
CREATE TABLE person_profiles (
    id               BIGSERIAL PRIMARY KEY,
    case_id          BIGINT NOT NULL UNIQUE REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    hair             VARCHAR(200),
    eyes             VARCHAR(200),
    skin_tone        VARCHAR(200),
    clothing         VARCHAR(500),
    accessories      VARCHAR(500),
    backpack         VARCHAR(200),
    shoes            VARCHAR(200),
    other_characteristics TEXT,
    searchable_text  TEXT,                        -- full-text searchable digest
    searchable_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(searchable_text,''))) STORED,
    embedding        VECTOR(512),                 -- mean of authorized photo embeddings
    embedding_model  VARCHAR(120),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_profile_search ON person_profiles USING GIN (searchable_tsv);
CREATE INDEX idx_profile_trgm   ON person_profiles USING GIN (searchable_text gin_trgm_ops);
CREATE INDEX idx_profile_vector ON person_profiles USING hnsw (embedding vector_cosine_ops);

-- ------------------------------------------------------------
-- Sightings
-- ------------------------------------------------------------
CREATE TABLE sightings (
    id                   BIGSERIAL PRIMARY KEY,
    sighting_reference   VARCHAR(20) NOT NULL UNIQUE,   -- e.g. ST-1189
    submitter_id         BIGINT NOT NULL REFERENCES users(id),
    case_id              BIGINT REFERENCES missing_person_cases(id),  -- optional association
    description          TEXT,
    clothing             VARCHAR(500),
    direction_of_movement VARCHAR(100),
    vehicle_info         VARCHAR(300),
    notes                TEXT,
    lat                  DOUBLE PRECISION,
    lng                  DOUBLE PRECISION,
    location_name        VARCHAR(255),
    captured_at          TIMESTAMPTZ,
    reported_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    source               VARCHAR(30) NOT NULL DEFAULT 'WEB',   -- WEB|MOBILE|VOICE|API
    status               VARCHAR(30) NOT NULL DEFAULT 'UNVERIFIED', -- UNVERIFIED|VERIFIED|REJECTED|DUPLICATE
    evidence_cluster_id  BIGINT,
    metadata             JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sightings_case   ON sightings (case_id);
CREATE INDEX idx_sightings_status ON sightings (status);
CREATE INDEX idx_sightings_geo    ON sightings (lat, lng);
CREATE INDEX idx_sightings_time   ON sightings (captured_at);

-- ------------------------------------------------------------
-- Evidence (files attached to sightings/cases)
-- ------------------------------------------------------------
CREATE TABLE evidence (
    id                BIGSERIAL PRIMARY KEY,
    sighting_id       BIGINT REFERENCES sightings(id) ON DELETE SET NULL,
    case_id           BIGINT REFERENCES missing_person_cases(id) ON DELETE SET NULL,
    uploader_id       BIGINT NOT NULL REFERENCES users(id),
    storage_key       VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255),
    content_type      VARCHAR(120),
    size_bytes        BIGINT,
    sha256            VARCHAR(64),
    malware_scan_status VARCHAR(30) NOT NULL DEFAULT 'PENDING', -- PENDING|CLEAN|SUSPICIOUS|FLAGGED
    quality_score     DOUBLE PRECISION,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidence_sighting ON evidence (sighting_id);
CREATE INDEX idx_evidence_case     ON evidence (case_id);
CREATE INDEX idx_evidence_sha256   ON evidence (sha256);

-- ------------------------------------------------------------
-- Evidence embeddings (pgvector)
-- ------------------------------------------------------------
CREATE TABLE evidence_embeddings (
    id                BIGSERIAL PRIMARY KEY,
    evidence_id       BIGINT NOT NULL UNIQUE REFERENCES evidence(id) ON DELETE CASCADE,
    embedding         VECTOR(512) NOT NULL,
    model_version_id  BIGINT,
    dimension         INT NOT NULL DEFAULT 512,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidence_embeddings_vec ON evidence_embeddings USING hnsw (embedding vector_cosine_ops);

-- ------------------------------------------------------------
-- Evidence clusters (duplicate-sighting grouping)
-- ------------------------------------------------------------
CREATE TABLE evidence_clusters (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    centroid        GEOMETRY(Point, 4326),
    first_timestamp TIMESTAMPTZ,
    last_timestamp  TIMESTAMPTZ,
    source_count    INT NOT NULL DEFAULT 1,
    avg_similarity  DOUBLE PRECISION,
    meta            JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sightings ADD CONSTRAINT fk_sightings_cluster
    FOREIGN KEY (evidence_cluster_id) REFERENCES evidence_clusters(id) ON DELETE SET NULL;

-- ------------------------------------------------------------
-- Potential matches (AI lead queue — HUMAN VERIFICATION REQUIRED)
-- ------------------------------------------------------------
CREATE TABLE potential_matches (
    id                 BIGSERIAL PRIMARY KEY,
    case_id            BIGINT NOT NULL REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    sighting_id        BIGINT NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
    evidence_id        BIGINT REFERENCES evidence(id) ON DELETE SET NULL,
    overall_score      DOUBLE PRECISION NOT NULL,
    face_similarity    DOUBLE PRECISION,
    clothing_similarity DOUBLE PRECISION,
    accessory_similarity DOUBLE PRECISION,
    body_similarity    DOUBLE PRECISION,
    image_similarity   DOUBLE PRECISION,
    location_relevance DOUBLE PRECISION,
    time_relevance     DOUBLE PRECISION,
    text_similarity    DOUBLE PRECISION,
    status             VARCHAR(30) NOT NULL DEFAULT 'AWAITING_REVIEW', -- AWAITING_REVIEW|ACCEPTED|REJECTED|MORE_INFO|DUPLICATE|ESCALATED
    explanation        JSONB,
    limitations        JSONB,
    model_version_id   BIGINT,
    reviewed_by        BIGINT REFERENCES users(id),
    reviewed_at        TIMESTAMPTZ,
    review_notes       TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_matches_case_status ON potential_matches (case_id, status);
CREATE INDEX idx_matches_score       ON potential_matches (overall_score DESC);
CREATE INDEX idx_matches_sighting    ON potential_matches (sighting_id);

-- ------------------------------------------------------------
-- Verification records
-- ------------------------------------------------------------
CREATE TABLE verification_records (
    id                 BIGSERIAL PRIMARY KEY,
    potential_match_id BIGINT NOT NULL REFERENCES potential_matches(id) ON DELETE CASCADE,
    reviewer_id        BIGINT NOT NULL REFERENCES users(id),
    decision           VARCHAR(30) NOT NULL,   -- ACCEPT|REJECT|MORE_INFO|DUPLICATE|ESCALATE
    notes              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_verification_match ON verification_records (potential_match_id);

-- ------------------------------------------------------------
-- Locations
-- ------------------------------------------------------------
CREATE TABLE locations (
    id              BIGSERIAL PRIMARY KEY,
    case_id         BIGINT REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    sighting_id     BIGINT REFERENCES sightings(id) ON DELETE CASCADE,
    geom            GEOMETRY(Point, 4326),
    label           VARCHAR(255),
    location_type   VARCHAR(40),        -- LAST_KNOWN|SIGHTING|RESOURCE|IMPORTANT
    accuracy_meters DOUBLE PRECISION,
    occurred_at     TIMESTAMPTZ
);
CREATE INDEX idx_locations_geom ON locations USING GIST (geom);
CREATE INDEX idx_locations_case ON locations (case_id);

-- ------------------------------------------------------------
-- Search zones (AI-assisted, requires investigator review)
-- ------------------------------------------------------------
CREATE TABLE search_zones (
    id         BIGSERIAL PRIMARY KEY,
    case_id    BIGINT NOT NULL REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    zone_type  VARCHAR(40) NOT NULL,      -- HIGH_PRIORITY|MEDIUM_PRIORITY|LOW_PRIORITY|LEAD_CLUSTER
    priority   INT NOT NULL DEFAULT 3,
    radius_km  DOUBLE PRECISION,
    geom       GEOMETRY(Polygon, 4326),
    rationale  TEXT,
    ai_generated BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_search_zones_geom ON search_zones USING GIST (geom);
CREATE INDEX idx_search_zones_case ON search_zones (case_id);

-- ------------------------------------------------------------
-- Case timeline
-- ------------------------------------------------------------
CREATE TABLE case_timeline (
    id           BIGSERIAL PRIMARY KEY,
    case_id      BIGINT NOT NULL REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    actor_id     BIGINT REFERENCES users(id),
    event_type   VARCHAR(40) NOT NULL,
    description  TEXT,
    payload      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_timeline_case ON case_timeline (case_id, created_at);

-- ------------------------------------------------------------
-- Notifications
-- ------------------------------------------------------------
CREATE TABLE notifications (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(40) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    body            TEXT,
    related_case_id BIGINT REFERENCES missing_person_cases(id) ON DELETE CASCADE,
    read            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_user ON notifications (user_id, read, created_at DESC);

-- ------------------------------------------------------------
-- Audit logs (append-only)
-- ------------------------------------------------------------
CREATE TABLE audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    actor_id      BIGINT,
    action        VARCHAR(80) NOT NULL,
    resource_type VARCHAR(60),
    resource_id   VARCHAR(60),
    ip_address    VARCHAR(64),
    user_agent    VARCHAR(500),
    details       JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_actor ON audit_logs (actor_id, created_at);
CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id);

-- ------------------------------------------------------------
-- Abuse reports
-- ------------------------------------------------------------
CREATE TABLE reports (
    id            BIGSERIAL PRIMARY KEY,
    reporter_id   BIGINT NOT NULL REFERENCES users(id),
    resource_type VARCHAR(40) NOT NULL,   -- SIGHTING|EVIDENCE|USER|CASE
    resource_id   VARCHAR(60),
    reason        TEXT NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'OPEN',  -- OPEN|IN_REVIEW|RESOLVED|DISMISSED
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Model versions (AI analytics / A/B)
-- ------------------------------------------------------------
CREATE TABLE model_versions (
    id              BIGSERIAL PRIMARY KEY,
    version         VARCHAR(40) NOT NULL UNIQUE,
    name            VARCHAR(120),
    face_model      VARCHAR(120),
    embedding_model VARCHAR(120),
    detection_model VARCHAR(120),
    metrics         JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE|BETA|RETIRED
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE evidence_embeddings ADD CONSTRAINT fk_emb_model
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL;
ALTER TABLE potential_matches ADD CONSTRAINT fk_match_model
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL;
