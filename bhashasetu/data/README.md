# data/

Dataset-side of BhashaSetu. **The moat.** Everything consent/rights-sensitive is
gitignored (`raw/`, `keypoints/`, `annotations/`); only schemas, glossaries, provenance
indexes, and generated manifests are committed.

| Path | Contents |
| --- | --- |
| `schema/sample.schema.json` | JSON schema for every sample record (validates ship-blocking fields) |
| `glossaries/{meta,pds,health,legal}.json` | Domain-scoped vocabularies (labels + handshape/regional notes) |
| `sourced/sources.csv` | Provenance index of candidate external sources (see `docs/SOURCING.md`) |
| `manifests/` | Versioned, exportable dataset manifests (only consented + QA-passed samples) |
| `raw/` | Raw videos (gitignored) |
| `keypoints/` | MediaPipe keypoints, JSON per sample (gitignored) |
| `annotations/` | JSONL label/vote/QA/consent logs written by the labeling tool (gitignored) |

## Glossaries

Starter seed only. Schema in `data/glossaries/meta.json`. Target: **500–1000 signs per
domain**, ≥5 clips per sign per region. Entries carry `source_ref` to a provenance source
and `regional_variants` notes so dialect-aware training/QA are possible.

## Manifest export rule

A sample is only eligible for a manifest when **all** of:

1. consent = granted (with a `form_id`),
2. ≥2 annotator labels agree above the consensus threshold (see `labeling/backend/consensus.py`),
3. QA = passed,
4. keypoints exist and pass basic validity (`labeling/backend/`) — enforced in increment (b).

## Sample ID scheme

`ISL-<DOMAIN>-<5-digit zero-padded>` — e.g. `ISL-PDS-00042`, `ISL-HTH-00101`, `ISL-LEG-00007`.