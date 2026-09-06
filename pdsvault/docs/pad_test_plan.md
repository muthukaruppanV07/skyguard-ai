# PDSVault — ISO/IEC 30107-3 PAD Test Plan

Presentation Attack Detection evaluation, Level 1 (construction) and Level 2
(performance).  The scoring helper (`APCER`, `BPCER`) and the deterministic
rig are implemented in `src/pdssec/pad.py` and exercised in
`tests/test_pad.py`; this is the field/committee-level plan for the actual
sensor.

---

## 1. Definitions

- **PAI (presentation attack instrument):** prop or replay (printed photo,
  photo on screen (video replay), 3D/silicone mask, paper cutout).
- **APCER (attack presentation classification error rate):** proportion of
  attack presentations incorrectly accepted as live.
- **BPCER (bonafide presentation classification error rate):** proportion of
  live presentations incorrectly rejected.
- **IAPMR (Impostor Attack Presentation Match Rate):** how often the impostor
  both passes PAD *and* matches the enrolled victim (reported, not
  optimised, because the matcher threshold handles FAR).
- Reporting per ISO/IEC 30107-3 §6 and the format required by the adopting
  regulator/tender.

## 2. Rig setup

- Capture device is the final target sensor (IR/stereo whenever available;
  the reference rig runs in RGB-only mode with the same estimator to keep CI
  deterministic).
- Enrolment: each subject enrolled once; templates encrypted and domain-held.
- Bonafide set: 100 subjects × 10 presentations.
- Attack sets per subject, 30 PAIs each:
  - P1 printed photo (flat, laminated);
  - P2 photo on a 7" screen (static);
  - P3 video replay of the subject on the phone screen;
  - P4 3D/silicone mask;
  - P5 paper cutout of the face.
- Lighting: three conditions (controlled 300 lx, dim 40 lx, outdoor glare);
  blocked at least two, to catch threshold/binarisation oversteer.
- Acceptance threshold: chosen so BPCER = 0 on the bonafide set, or the
  regulator-mandated APCER ceiling — whichever is stricter.

## 3. Procedure (Level 2, per ISO/IEC 30107-3)

1. Collect bonafide presentations; run the estimator; record scores.
2. For each PAI type, stage presentations per the §6 table; record scores.
3. Compute APCER per PAI and overall, BPCER, and IAPMR.
4. Sweep the acceptance threshold and produce the EER / ROC curve; pick the
   operating point; confirm the required (APCER, BPCER) pair is inside the
   curve.
5. Report with per-PAI APCER broken down by lighting condition.

## 4. Pass criteria (target for the current reference rig)

| Measure | Target |
|---|---|
| APCER (overall, at operating threshold) | ≤ 1.5% |
| APCER per PAI (printed / video / mask / cutout) | the dominant failure type is *ranked* per test — see `test_apcer_per_attack_type_ranked` — and each is below the overall ceiling at the chosen threshold |
| BPCER at the chosen threshold | 0% (by construction) on the rig |
| IAPMR | reported for the record; bounded by the matcher threshold (not PAD) |
| Determinism | synthetic rig reproduces identical numbers across runs and OSes |

## 5. The reference rig

The reference implementation ships a deterministic, reproducible rig so that
CI and field tests speak the same numbers:

- `generate_rig()` builds a labelled bonafide + attack dataset with fixed
  seeds (rendering is a stand-in for the real sensor; real-sensor data plugs
  into the same evaluator).
- `evaluate_rig()` returns `APCER` overall + per PAI, `BPCER`, and a
  threshold sweep.
- `tests/test_pad.py` pins: deterministic output, threshold selection
  behavior, distinct attack types, presence of labels, per-attack ranking,
  and monotonic BPCER vs threshold.

Command line: `python -B -m pdssec.cli pad-report` (prints the current
table).

## 6. Field acceptance

For production: the same procedure must run on three field units × three
locations; a PAD performance delta &gt; 5 p.p. between units is a failed
batch (sensor variance).  Any model/sensor change re-runs §3 in full.

## 7. Limitations to disclose honestly

- The reference rig is suite-reproducible, not real-sensor data; the
  production number must come from the actual capture device.
- Presentation attack detection is a race with (currently unknown to us)
  novel PAI – the liveness module is upgradeable and kill-switchable, and
  the weekly model/update channel ships PAD improvements.
- Angular/occlusion envelopes are tested on the matcher side (FRR), not
  PAD; a beneficiary wearing a tight mask may hit the PAD envelope before
  the matcher does (BPCER will show it, and BPCER &gt; 0 is exactly the
  affordance that four-eyes override exists for).