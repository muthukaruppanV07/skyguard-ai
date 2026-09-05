# CONSENT.md — Consent + ethics protocol

Applies to every clip in the BhashaSetu corpus, whether recorded by us or sourced.

## Consent (recording)

Every signer must complete a consent form **before** recording starts. `consent_forms/`
holds signed copies (paper scans or e-sign), and the sample record stores `consent.form_id`.

Consent form fields:

- Who (anonymous descriptor only on the form itself: initials, region, age range, gender,
  handedness, native/acquired signer, Deaf/hearing, education level).
- What will be recorded (video of upper body signing; optionally audio of the request
  they are signing).
- Data uses: (a) training models, (b) public dataset release, (c) UI demo, (d) research
  publication. **Per-sample opt-in via checkboxes** — defaults off.
- Data lifetime + right to withdraw (withdrawal removes video+keypoints, keeps an audit
  marker only).
- Contact for questions/withdrawal (in ISL-friendly format: text + sign-language video).
- Signer copies, numbered, signed, witnessed where required.

## Consent (sourced clips)

For external clips:

- Provenance must include the source's license/permission (`docs/SOURCING.md`).
- If the source is a community educator, we request **written permission** (email) before
  including the clip in any release; the email is the permission record.
- Government/public-work assets: confirm the specific reuse terms; record them.

## Anonymization

1. No names, no Aadhaar, no identifying documents in/on any sample or metadata.
2. Signers get anonymous IDs `S-###`; the mapping is retained only in an access-controlled
   file (never in git, never in manifests).
3. Video: faces may be blurred/occluded for opt-in "stats only" uploads.
4. Keypoint storage separates pose/hand from face; face landmarks are never uploaded by
   default — only aggregate stats, and only when the signer opts in.

## Signer diversity tracking — the training anti-bias requirement

Per-signer metadata (age range, gender, region, handedness, native/acquired) is stored in
the consent record and aggregated by the labeling tool (`/api/stats`). The labeling and
train/eval splits MUST track diversity so we can:

- Split **by signer identity** (never by clip — sneaky leakage otherwise).
- Report bias across demographics (`docs/BIAS_REPORT.md`).
- Actively recruit under-represented groups (older signers, regional dialect signers).

## Withdrawal workflow [collective standard]

1. `POST /api/consent/withdraw {signer_id, form_id}` → immediately marks all samples by
   that signer `status=withdrawn`.
2. Withdrawn samples are excluded from manifests and from any subsequent model training.
3. Raw video + keypoints for that signer are deleted per the deletion policy in the
   consent form; an audit marker (timestamp, count removed) remains in the consent log.

## QA pass guardrails

- The QA reviewer checks for **garbage samples**: out-of-frame hands, wrong-person
  signing, truncated gloss, mislabeled metadata, duplicated clips. Decision
  `pending → passed | rejected` recorded in the QA log.
- Rejected samples never reach manifests. A rejected sample can be re-recorded, not edited.

## Ethics notes

- Pay/minor/student signers: per institutional and Indian labour norms; minors need a
  parent/guardian signature on the same form.
- Court use: output must be **explainable to the deaf user first** (gloss + confidence on
  screen) and logged; a translator should be the point of record, the tool is a support.
- This project must not claim "fully accurate automatic interpretation" — it is *assisted
  translation*, and handles low confidence by asking the user to repeat.