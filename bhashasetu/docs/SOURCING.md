# SOURCING.md — Seed data sourcing protocol

Seed data is **not** scraped. Every clip we take from an external source must have a
provable right-to-use, and every clip we record must have informed consent.

## Step 1 — Inventory candidate sources

Add rows to `data/sourced/sources.csv`. Known primary sources (verify current URLs +
licenses manually before harvest; dates must be recorded):

| Source | Kind | What it gives | Licence posture (verify per clip) |
| --- | --- | --- | --- |
| **ISLRTC** (Indian Sign Language Research & Training Centre, Delhi, Ministry of Social Justice & Empowerment) — `islrtc.nic.in` + YouTube `ISLRTC` | Government / public | Official ISL glossary videos, dictionary content, tutorials | Government work product — confirm publication terms + permission for reuse in a training dataset |
| **AYJNISHD** (Ali Yavar Jung National Institute of Speech & Hearing Disabilities, Mumbai) | Government institute | Teaching videos, ISL instructional content | Confirm terms per asset |
| **NISHTHA** (NCERT teacher-training modules on inclusive education) | Government programme | ISL basics videos (teacher-focused) | Confirm terms per asset |
| **NISH Trivandrum** (National Institute of Speech & Hearing) | Institute | ISL content | Confirm terms per asset |
| **Deaf Can Foundation (Bengaluru)** — ISL dictionary / app, YouTube | NGO | Sign dictionary entries | Verify individual video licenses / reach out for written permission |
| **Community ISL educators on YouTube** (ISL teachers, Deaf creators) | Community | Regional dialect examples, natural signing | **Must request written permission per channel/clip**; many are personal content |
| **Institutional ISL dictionaries** (ISLRTC dictionary volumes, RKMVERI dictionary work) | Published dictionary | Lexical reference (not video) | Cite; do not copy media without license |
| **Self-recorded sessions** | Primary | Gold-standard consented data with full metadata | Our own consent forms (`docs/CONSENT.md`) |

## Step 2 — Per-clip provenance record

Every harvested clip gets a provenance entry (in `data/sourced/` or, once registered, in
the sample record):

```json
{
  "source_id": "ISLRTC-0142",
  "source_name": "ISLRTC Official",
  "url": "https://.../video...",
  "accessed_on": "2026-08-19",
  "license": "government-publication",
  "permission_record": "email-2026-08-19-islrtc-reuse-ok.txt",
  "dialect_region": "delhi",
  "clip_note": "2-handed production; fingerspelling of 'AADHAAR'",
  "harvested": true,
  "registered_sample_id": "ISL-PDS-000123"
}
```

**Rules**

1. No screenshot/video reuse without a documented right. If unsure → **exclude**.
2. `dialect_region` is mandatory (this is our differentiator vs. naive models).
3. Sourced clips used in a *public* dataset must carry the source's license; recorded
   clips must carry a consent form ID.
4. Do not scrape en-masse. Harvest only what the labeling pipeline can process in a week.

## Step 3 — From source to sample

1. Clip downloaded → `data/sourced/clips/` (gitignored) with a `provenance.json`.
2. Registered in the labeling tool as a sample with `source` metadata + dialect tag.
3. Keypoints extracted (increment b) → `data/keypoints/`.
4. Labeled by ≥2 annotators → consensus → QA pass → eligible for manifest export.

## Step 4 — Bulk upload pipeline (drop-in approved videos)

For clips you already have **with documented permission** (recorded or licensed), use the
one-shot ingest path instead of the UI's one-at-a-time register form:

1. Drop the clips into `data/raw/uploads/` and (optionally) their keypoints into
   `data/keypoints/` (keypoint extraction arrives in increment b).
2. Fill in `data/sourced/upload-manifest.csv` — one row per clip. Columns:

   `domain, signer_id, region, video_path, keypoints_path, gloss, consent_form_id,
   consent_status, source_kind, source_url, notes`

   - `signer_id` must already have a **granted** consent record (`S-###`).
   - `consent_form_id` must match the consent log.
   - `video_path` is relative to `data/` and must exist — URLs are **not** fetched.
3. Run:

   ```powershell
   python labeling/scripts/import_videos.py              # validates + registers
   # or, to generate a blank template first:
   python labeling/scripts/import_videos.py --template > my-upload.csv
   ```

   The importer validates domain/region/consent, skips already-registered clips
   (idempotent), and prints an OK/FAIL/SKIP summary with a non-zero exit code if any
   row failed.

4. New samples land in the queue as `registered` and await ≥2 annotator votes + QA
   before they can be shipped in a manifest.

### Recording in the browser (real video, consent-first)

The labeling UI's **Record video** tab captures real clips straight from a webcam,
fully offline:

1. The signer must first have a **granted consent record** (Register tab).
2. Pick the consented signer, domain, and a gloss hint, then Start camera →
   ● Record → ■ Stop. The recording is reviewed locally before saving.
3. Saving requires ticking the **consent acknowledgment** — the saved video is
   registered with `consent=granted` + the signer's `form_id` attached.
4. Uploads land in `data/raw/uploads/` and stream back over `/media/` for review.

This is how **real, permissioned ISL video** enters the corpus without any third-party
scraping. (Synthetic clips via `gen_synthetic_videos.py` remain available for pipeline
testing.)

### Synthetic test videos (dev only)

`python labeling/scripts/gen_synthetic_videos.py --count N` renders N playable h264
clips whose motion matches synthetic keypoints, writes them + an `upload-manifest.csv`
for `import_videos.py`. This exercises the full video pipeline (render → import →
stream → overlay) before real camera capture ships in increment (b). Requires a one-time
`python -m pip install imageio-ffmpeg` (a static ffmpeg binary; nothing else).

## Dialect regions (seed taxonomy)

Use the standard `region` codes in `data/glossaries/meta.json`:

`delhi`, `mumbai` (mh), `kolkata` (wb), `chennai` (tn), `bengaluru` (ka), `hyderabad`
(tg), `lucknow` (up), `patna` (br), `gujarat` (gj), `punjab` (pb), `kerala` (kl),
`odisha` (od), `northeast` (ne), `central` (mp), `j&k` (jk).

Variation notes are free text per sample (`regional_variants`), e.g. "Chennai sign for
RATION uses two open-B hands; Delhi uses pinched thumb-index at the side."

## Priority order for the first 1K

1. **PDS** — most scripted interactions (quota, tokens, documents) → highest ROI, easiest
   to standardize templates for.
2. **Health** — emergency/safety-critical glosses first (pain, fever, medicine, referral,
   wheelchair, emergency).
3. **Legal** — glosses with legal weight (petition, bail, affidavit, witness); lowest
   volume, highest care around accuracy.
