# DATA_GAP.md — The ISL data gap (BhashaSetu's moat)

## Why ISL is unlike ASL

| Factor                          | ASL                                   | ISL                                   |
| ------------------------------- | ------------------------------------- | ------------------------------------- |
| Public labeled datasets         | WLASL, MS-ASL, etc. (10k–200k clips)  | **Effectively none published**        |
| Handshape models                | Numerous (PoseAH, handshape datasets) | **No Indian handshape model exists**  |
| Variation                       | Mostly 1-handed, moderate regional    | **2-handed dominant**, massive regional variation (Deaf community is not centralized; regional dialects per state/Deaf school) |
| Grammar standardization         | Well-documented                       | Documented but fragmented (OSV, no copula) |
| NLG / avatar resources          | Rich (SignWriting, HamNoSys, avatars) | **Minimal**                          |

Consequence: any competitor shipping a "generic sign language" model (trained on ASL or
single-dialect data) will **fail in the field** on real Indian signing. Success requires:

1. Owning a **curated, consent-compliant, region-tagged ISL dataset**.
2. A **signer-invariant** training recipe that works with a few hundred samples/signer.
3. **Domain-scoped** vocabularies (PDS / health / legal) rather than a sprawling dictionary.

## Working target

- **~500–1000 signs per domain** (3 domains → 1.5K–3K glosses of coverage).
- **≥5 clips per sign per region**, split **by signer identity** for honest evaluation.
- Self-supervised pretraining on **unlabeled** ISL video (bootstraps with ~zero labels).
- With only ~1K labeled samples per domain the classifier must still reach usable
  accuracy — every advanced feature is justified against this constraint.

## Cold-signer problem (the real eval)

Signer-independent accuracy is the metric that matters for government kiosks, because a
new user walks up cold every time. We evaluate:

- Per-class accuracy + confusion matrix (per domain).
- **Cold-signer eval**: train on signer set S, evaluate on signers never seen in
  training (adversarial domain adaptation, target "unseen signer").
- Dialect-held-out eval: train on North India dialects, eval on South (and vice-versa).
- Bias report across age, gender, handedness, region (see `docs/BIAS_REPORT.md` once models exist).

## Dataset versioning

Every release is a **manifest** (`data/manifests/`) that pins:

- `schema_version`, `dataset_version`, timestamp.
- One record per sample: `sample_id`, domain, gloss(es), signer (anon), region/dialect,
  consent form id, QA status, source provenance, keypoint stats, label votes + consensus.
- Checksums (sha256) for raw video + keypoints so a later release is reproducible.

Raw video and keypoints live in `data/raw` / `data/keypoints` (gitignored). The manifest
is the only thing that ships in git; media is distributed separately with a data license.

## What we do NOT store

- No names, Aadhaar numbers, or any PII in datasets. Signers are `S-###` anonymous IDs.
- No facial/voice biometric identities. Keypoints may be extracted from faces only as
  anonymized landmark stats, never uploaded except as aggregate, opt-in stats.
