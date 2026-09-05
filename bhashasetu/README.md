# BhashaSetu

Real-time **Indian Sign Language (ISL) → speech** translation for government services
(PDS shops, hospitals, courts). Designed for **offline/edge** deployment (Raspberry Pi 4 /
Android Go kiosks), 2-handed ISL, regional variation, and Aadhaar-linked workflows.

> The moat is the **data gap**: ISL has almost no public labeled dataset, no Indian
> handshape model, and massive regional / 2-handed variation (unlike ASL). Every
> component in this repo is designed to maximize accuracy with **~1K samples per domain**.

## Repo layout

| Path          | Purpose                                                                    |
| ------------- | -------------------------------------------------------------------------- |
| `data/`       | Seed-data provenance, domain glossaries, sample schema, manifests          |
| `labeling/`   | Web-based annotation tool (keypoint overlay, multi-annotator voting, QA)   |
| `models/`     | Train/eval for isolated-sign POC → continuous spotting (future increments) |
| `speech/`     | TTS + text-to-ISL avatar (future increments)                               |
| `deploy/`     | Edge runtime, quantization, graceful degradation (future increments)       |
| `docs/`       | Data-gap analysis, sourcing protocol, consent/ethics, ISL grammar, bias    |

## Incremental plan

1. **(a) dataset + labeling tool** ← *current increment*
2. (b) keypoint extraction (MediaPipe)
3. (c) isolated-sign classifier POC
4. (d) signer-invariance + self-supervised pretraining
5. (e) continuous spotting (CTC/transformer, WER benchmark)
6. (f) NLG (OSV→English) + conversational state machine
7. (g) edge quantization (TFLite/ONNX 4-bit) + avatar

Each increment must *run and be verified* before the next. Small-data is the
organizing principle: every advanced feature must answer *"does this make us more
accurate with only 1K samples per domain?"*

## Quick start (current increment)

```powershell
# No pip installs required.
# 1) optional: seed a realistic demo corpus (consented signers, synthetic keypoints,
#    votes, QA passes, manifest) so the UI is not empty:
python labeling/scripts/seed_demo.py

# 2) optional: render 12 playable synthetic test videos + imports them
python labeling/scripts/gen_synthetic_videos.py --count 12   # one-time: pip install imageio-ffmpeg
python labeling/scripts/import_videos.py

# 3) start the labeling server:
python labeling/backend/server.py --port 8123
# 4) open http://localhost:8123/

Add your **own approved videos** (per docs/SOURCING.md): drop clips into
`data/raw/uploads/`, fill `data/sourced/upload-manifest.csv`, run `import_videos.py`.
Or record real video directly in the browser via the **Record video** tab (needs a
consented signer first).

Run tests:

```powershell
python -m unittest discover -s labeling/backend -p "test_*.py" -v
```

## Labeling capabilities (increment a)

- Keypoint-overlay playback (MediaPipe JSON schema) over video, plus a
  keypoints-only scrubber for clips without a video file.
- OVS-grammar annotation with glossary autocomplete (PDS / health / legal seeds).
- Multi-annotator voting with consensus status (agreed / ambiguous / needs_voting)
  and per-annotator latest-wins votes.
- QA gate (pass/reject), consent registry + one-click withdrawal, signer-diversity
  stats, and a versioned manifest exporter with sha256 checksums (only consented +
  voted + QA-passed samples ship in manifests).
- Append-only JSONL store under `data/annotations/` with an audit log — every
  mutation is recorded for governance.

## Design rules

- **Privacy by design** — everything on-device; only anonymized keypoint *stats*
  are ever eligible for upload. Consent trail is mandatory per sample.
- **Governance-grade** — every translation session is logged (timestamp, anonymized
  signer ID, gloss, output, confidence) for legal/official record.
- **Explainability** — the UI always shows recognized glosses + per-gloss confidence
  to the deaf user *before* speech is spoken; low confidence ⇒ "please repeat",
  never a hallucinated word.
