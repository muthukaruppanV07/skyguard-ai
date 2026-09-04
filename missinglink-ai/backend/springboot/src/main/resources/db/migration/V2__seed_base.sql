-- ============================================================
-- MISSINGLINK AI — V2: base seed (roles, permissions, admin)
-- ============================================================

INSERT INTO roles (name, description) VALUES
  ('PUBLIC_USER',   'Can submit sightings, report missing people, browse public cases.'),
  ('FAMILY',        'Can create and manage authorized cases for a missing person.'),
  ('INVESTIGATOR',  'Authorized authority: verifies sightings, reviews matches, coordinates search.'),
  ('ADMIN',         'System administration: users, permissions, audit, config, AI model settings.');

INSERT INTO permissions (name, description) VALUES
  ('case:create',        'Create a missing-person case'),
  ('case:read',          'Read case details within authorization'),
  ('case:update',        'Update case details'),
  ('case:status',        'Change case status / priority'),
  ('case:delete',        'Soft-delete cases (admin)'),
  ('case:public-search', 'Browse public active cases'),
  ('photo:upload',       'Upload authorized photographs'),
  ('sighting:submit',    'Submit a sighting'),
  ('sighting:read',      'Read sighting details'),
  ('sighting:review',    'Verify/reject/duplicate sightings'),
  ('evidence:upload',    'Upload evidence'),
  ('evidence:read',      'Read evidence metadata'),
  ('evidence:download',  'Download evidence via signed URL'),
  ('match:review',       'Review AI potential matches and decide'),
  ('geo:view',           'View geospatial intelligence'),
  ('geo:write',          'Generate search zones'),
  ('notification:read',  'Read own notifications'),
  ('audit:read',         'Read audit logs'),
  ('admin:manage',       'Manage users, roles, config'),
  ('report:create',      'File an abuse report'),
  ('report:review',      'Review abuse reports');

-- PUBLIC_USER
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name='PUBLIC_USER'
  AND p.name IN ('sighting:submit','case:public-search','evidence:upload','report:create','notification:read');

-- FAMILY
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name='FAMILY'
  AND p.name IN ('case:create','case:read','case:update','photo:upload','sighting:submit',
                 'evidence:upload','evidence:read','notification:read','report:create','case:public-search');

-- INVESTIGATOR
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name='INVESTIGATOR'
  AND p.name IN ('case:read','case:update','case:status','sighting:read','sighting:review',
                 'evidence:read','evidence:download','evidence:upload','match:review',
                 'geo:view','geo:write','notification:read','case:public-search','report:create');

-- ADMIN
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name='ADMIN';

-- Model version registry (one initial version; embeddings reference it)
INSERT INTO model_versions (version, name, face_model, embedding_model, detection_model, status, metrics)
VALUES ('v1.0.0', 'MissingLink vision v1', 'fallback-histogram/v1', 'opencv-histogram/v1', 'fallback/v1',
        'ACTIVE',
        jsonb_build_object('dimension', 512, 'cosine_floor', 0.35, 'min_overall', 0.55, 'env', 'DEMO_FALLBACK'));
