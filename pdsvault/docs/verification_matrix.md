# PDSVault — Verification Matrix

Maps every threat from `docs/threat_model.md` to its mitigation, the
enforcing test, and the observed result in the reference implementation.
**This document and `pytest tests` must stay in agreement: if a matrix row's
test turns red, the row is updated to `FAIL` and the code is fixed before
release — never the reverse.**

Legend: ✔ enforced by the reference implementation and green in `tests/`;
◐ enforced at the policy/protocol level (reference shows the mechanism);
✘ not enforced (explicitly out of scope / residual risk, listed in
threat_model §Residual).

## 1. Adversarial model recap

Threats T1–T14 are defined in `docs/threat_model.md` §Threats.  This matrix
covers every T-number so the enforcement story is complete.

## 2. Identity & biometrics

| Threat | Mitigation (protocol/device) | Enforcing test | Result |
|---|---|---|---|
| T1 forgery / synthesis, T2 deepfake at capture | ISO 30107-3 PAD (sensor fusion + HW signals); FAR 1e-4 per comparison, 1:N-calibrated; two-tier thresholds | `tests/test_pad.py` (APCER per attack type; threshold sweep; BPCER monotonic) | ✔ |
| T3 stolen cache → template replay, cross-shop link | UID never stored; masked dsid domain-scoped; per-shop domain keys; templates encrypted under derived per-shop key; no device holds master keys | `test_crypto::test_masked_uid_domain_scoped`, `test_domain_template_keys_distinct`, `test_domain_keys_encrypt_template`, `test_beneficiary_record_sign_verify_and_masking` | ✔ |
| T4 face-match bypass / impostor | cosine match at operating point; impostor rejected at point of use; every failure hash-chained | `test_entitlement::test_impostor_match_fail`, `test_all_verifications_recorded_in_ledger` | ✔ |
| T5 PAD bypass, presentation attacks (printed photo, video replay, masks) | PAD rig scores APCER per attack; threshold chosen so overall APCER ≤ 1.5% at BPCER 0 | `test_pad::test_apcer_per_attack_type_ranked`, `test_threshold_selection_meets_targets` | ✔ |
| T6 template poisoning / feature-space confusion | templates versioned; embedding space pinned per model; signature-verified records; needs_reenroll migration | `test_store::test_signed_beneficiary_applied`, `test_unsigned_beneficiary_quarantined` | ✔ |

## 3. Device & key compromise

| Threat | Mitigation | Enforcing test | Result |
|---|---|---|---|
| T7 seized device → key extraction | storage key sealed to TPM PCR policy; SRK/EK never leave chip; keys wiped after use; data minimised (no full UID) | `test_crypto::test_mock_tpm_seal_unseal_policy`, `test_fake_tpm_is_detected_by_quote` | ✔ |
| T8 device reflash / rollback / counterfeit TPM | PCR-12 measurement chain; TPM2 monotonic NV counter (anti-rollback); attestation quote on every sync; counterfeit TPM fails closed | `test_crypto::test_mock_tpm_anti_rollback_counter`, `test_faults::test_nv_rollback_detected_by_monotonic_counter`, `test_faults::test_fake_tpm_breaks_device_replace_fails_closed` | ✔ |
| T9 clock rewinding (stale-window revival) | signed clock anchors; monotonic local counter; tamper event + quarantine on backward jump; entitlement needs live anchor | `test_time.py` (5 tests: anchor, backward/forged anchor, wall-clock drift, monotonic source, safe-has-anchor), `test_entitlement::test_clock_rewind_fails_closed`, `test_faults::test_clock_rewind_tamper_event_and_quarantined_sync` | ✔ |
| T10 offline-cache poisoning | every record authority-signed; all persisted fields derived from signed body; point-of-use re-verification; quarantine | `test_store::test_poisoned_cache_signature_detected`, `test_faults::test_cache_byte_corruption_quarantined`, `test_fuzz::test_apply_record_rejects_hostile_blobs` | ✔ |
| T11 database tamper (row edit, token reuse) | append-only Merkle ledger; periodic signed root anchors; token local-double-spend denial | `test_ledger.py` (inclusion proof, gap detection, root-mismatch, anchoring, append-only), `test_store::test_used_token_local_spend`, `test_entitlement::test_redeem_and_local_double_spend` | ✔ |
| T12 operator misuse / unreviewed override | signed operator log, hash-chained; four-eyes override with rate limits and provisional status | `test_entitlement::test_four_eyes_override_and_rate_limit`, `test_all_verifications_recorded_in_ledger` | ✔ |
| T13 data-theft at rest / via egress | SQLCipher-encrypted cache, TPM-sealed key, minimal on-device data, DP-noise on egress aggregates | `test_crypto::test_mock_tpm_seal_unseal_policy` (+ threat_model §Privacy) | ◐ |

## 4. Network & sync integrity

| Threat | Mitigation | Enforcing test | Result |
|---|---|---|---|
| T14 poisoned / replayed / stale snapshot | snapshot versioning + prev-hash chain; authority signature; per-device Merkle root; resumable chunked delta; quarantine of corrupt chunks | `test_sync::test_sync_replay_is_rejected`, `test_poisoned_snapshot_signature_rejected`, `test_malformed_record_quarantined`, `test_corrupt_chunk_quarantined_not_applied`, `test_faults::test_replayed_old_snapshot_rejected` | ✔ |
| Sync convergence after divergence | central uniqueness resolution; duplicate_flags + follow-up revocation + chargeback | `test_sync::test_divergent_shops_converge_at_server`, `test_property_sync_convergence`, `test_faults::test_cross_shop_double_dip_flagged_at_sync` | ✔ |
| Partial / torn sync (power cut) | chunked resumable delta; per-chunk hashes; state held until both seq+hash committed; re-sync repairs | `test_faults::test_partial_sync_retains_consistency` | ✔ |
| Stale epochs reviving entitlement | signed epochs expire at `valid_to` locally; property-tested | `test_sync::test_property_stale_epochs_never_revive` | ✔ |

## 5. Entitlement & double-spend

| Threat | Mitigation | Enforcing test | Result |
|---|---|---|---|
| Cross-shop double-dip offline | blinded tokens; uniqueness decided centrally at sync; duplicate flag + revocation + chargeback; second redemption denied locally if token already used | `test_sync::test_divergent_shops_converge_at_server`, `test_faults::test_cross_shop_double_dip_flagged_at_sync`, `test_entitlement::test_redeem_and_local_double_spend` | ✔ |
| Grace-window abuse | grace only within signed band + no local redemption + rate limits; authority re-deliberation at sync | `test_entitlement::test_grace_issue_allowed_within_band`, `test_grace_denied_after_redeem` | ✔ |
| Expired entitlement release | hard fail at `valid_to` with no signed extension | `test_entitlement::test_expired_entitlement_denied` | ✔ |
| Revoked beneficiary still served | revocation rows applied from snapshot; point-of-use check | `test_store::test_revocation_applies_and_blocks`, `test_entitlement::test_revoked_beneficiary_denied` | ✔ |
| Repeat-offender / brute-force | per-rs attempt budget; lockout + escalation | `test_entitlement::test_lockout_after_repeated_failures` | ✔ |

## 6. Robustness & failure containment

| Failure | Mitigation | Enforcing test | Result |
|---|---|---|---|
| Disk full mid-write | fail-closed: verification blocked, quarantine of partial state, no silent loss | `test_faults::test_disk_full_fails_closed` | ✔ |
| PAD rejected every bonafide (systematic) | BPCER sweep shows 0% at the chosen threshold; human-visible PAD diagnostics + override path (four-eyes) | `test_pad::test_sweep_monotonic_bpcer` | ✔ |
| Model forced into rollback | signed model versions, kill-switch honoured, no unsigned/old model accepted | `test_faults::test_model_kill_switch_blocks_update` | ✔ |
| Fuzzed/random input against parsers | canonical parser, frame decoder, SQL identifier filter, apply_record, signature verification all fuzz-tested, never crash | `tests/test_fuzz.py` (6 property tests) | ✔ |

## 7. Not enforced (residual risk — owned, not hidden)

| Residual | Who owns it | Why accepted |
|---|---|---|
| Physical PAD defeat on a specific live face with IR-grade hardware | supply-chain eval on final sensor (pending field procurement) | needs the actual sensor to characterise |
| Inside-job by the authority itself | authority key custody (HSM, split custody) | out of device scope |
| Side-channel on a tampered TPM with micro-probe lab | hardware cert (FIPS/CC, e.g. CC EAL4+ TPM) | reference uses a TPM2 mock |
| DoS on the shop line (queue flooding) | physical ops / state PDS | not a data-integrity issue |
| Full UID reidentification via strong side channel at the central authority | central ops | the mask is only as good as the authority's own data handling |

## 8. Regression gate

```text
python -B -m pytest tests -q
# must print 100% and 79 tests collected, zero failures, zero warnings->errors
```
The check runs at every release and is wired into CI as a required gate.