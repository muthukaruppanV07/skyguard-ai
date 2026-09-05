# PDSVault — Privacy Impact Assessment (PIA)

Scope: offline face-verified PDS entitlement terminal.  Aligns to the DPDP Act,
2023 (India), the UIDAI Offline KYC guidance, and ISO/IEC 27701 (privacy
information management).  This document is the privacy counterpart to
`threat_model.md`; it answers "what data exists, why, who can see it, and what
happens on a breach".

---

## 1. Data inventory

| Dataset | Contains | Purpose | Where it lives | Encryption | Also visible to |
|---|---|---|---|---|---|
| A. Beneficiary row | masked uid (`dsid`), domain-scoped; encrypted template; basket/epoch window; status; revocation marker | entitlement + face matching | device cache (`cache.sqlite`) | AES-GCM + SQLCipher at rest, TPM-sealed key | server (masked id + basket only) |
| B. Face template | 512-d embedding (or INT8 distil) | 1:N matching | device cache | AES-GCM under per-shop derived key | **never** egressed to server as-is |
| C. Verification/event log | signed `(dsid, verdict, when, who/operator, reason)` | audit, dispute, fraud | device ledger + server mirror | at rest encrypted; content is minimal | server after sync |
| D. Sync evidence | used-token ids, ledger anchors, attestation quotes, clock readings | reconciliation, tamper detection | transit + server | TLS + signed payloads | server only |
| E. Operator session | operator id, action, override records | four-eyes, audit | device + server | signature-bound | server after sync |
| F. PAD frames | raw frames during a verification attempt | liveness; **not retained** | RAM, immediately discarded | n/a (in-memory) | nobody |

**Not collected:** full Aadhaar/UID number, name, gender, DOB, address, phone,
family graph, income, or any biometric modality other than the template
needed for matching.  This is the minimisation floor the rest of the PIA
builds on.

## 2. DPDP Act, 2023 mapping (India)

| DPDP obligation | How PDSVault meets it | Implementation |
|---|---|---|
| **Notice & purpose limitation** | capture-time notice placard + UI statement; templates used only for matching | `docs/training.md` §operator responsibilities; UI copy |
| **Data minimisation** | no UID/PII stored; masked ids only; template-only storage | §1 inventory; `crypto.py` masking |
| **Consent** | beneficiary consent captured at enrolment/KYC (offline token); template generation is covered by the same consent record | signed consent flag in beneficiary body |
| **Lawful processing** | statutory PDS purpose; DPDP lawful bases (consent + legal obligation) | documented in enrolment contract |
| **Data quality** | signed records; revocations; re-enrolment triggers | `schema.md`; `template_version`, `needs_reenroll` |
| **Storage limitation** | entitlement epochs expire; purge instructions delete rows on receipt; quarantine holds broken state only | `docs/runbook.md` §purge; `schema.md` |
| **Security safeguards** | zero-trust device, TPM-sealed keys, signed records, Merkle audit | `threat_model.md` T7–T14 |
| **Data breach notification** | a breach is detectable (attestation, tamper flags) and reportable within the statutory window | runbook §breach response |
| **Data principal rights** | correction/enrolment-review at the shop; erasure via signed purge instruction with erasure receipt | `architecture.md` §right-to-be-forgotten |

## 3. UIDAI offline-KYC mapping

| UIDAI guidance | PDSVault |
|---|---|
| Offline verification must not require Aadhaar authentication (OAuth/API) | verification is fully offline; no auth call exists in the local path (asserted in tests) |
| Masked Aadhaar (referential request unit) | masked uid, HKDF-scoped per shop; the shop can never re-derive the full number |
| No storage of the full Aadhaar | guaranteed by construction (no column, no field, no PII in the schema) |
| Paperless/QR references | enrolment token is QR/offline carry; the device reads only the signed payload |
| Consent + purpose limited to auth | consent captured at enrolment; template + mask pipeline is purpose-bound |

## 4. ISO/IEC 27701 (PIMS) mapping

| Clause area | Evidence |
|---|---|
| 7.2.2.2 privacy policy | PIA + training; policy is displayable in the operator UI |
| 7.2.3.3 privacy roles | owner: state PDS authority; processor: field operator; data principal: beneficiary |
| 7.2.5.2 purpose specification | §1 – each dataset has exactly one purpose |
| 7.2.5.3 lawfulness | §2 lawful bases |
| 7.2.5.4/5/6 minimisation, retention, accuracy | §1 + epoch expiry + signed records |
| 7.2.6.2/3/4 security of processing | T7–T14 + verification matrix |
| 7.3.6.2/3/4 breach mgmt | runbook §breach response |
| 8.4.2.1/2/3 PII-technical controls | access control, encryption, minimization by design |

## 5. Reidentification & linkage analysis

| Question | Answer |
|---|---|
| Can a reversed dsid reveal a UID? | No: `dsid = HMAC(mask_key_derived, uid)`, scoped per shop; mask_key_derived is server-side and domain-scoped; bruteforce of a 128-bit key is infeasible, and even the mapped id is meaningless outside the shop |
| Cross-shop correlation by template? | No: templates are AES-GCM-encrypted under a per-shop derived key that exists only on the server; raw embeddings never leave the device encrypted |
| Linking attacker with sync evidence? | Evidence carries masked ids + token ids only; DP-noise is applied to egress aggregates |
| Reidentifying from a stolen shop? | A full dump yields encrypted templates + masked ids; PIA FAQ + R5 of threat_model covers the residual (server-side correlation) |

## 6. Privacy breach scenarios & response

| Breach | Detection | Response | Time target |
|---|---|---|---|
| Stolen device + attempted decryption | attestation/tamper flags at next sync; storage key never unseals if PCR changed | report to authority; re-provision or retire device; rotate per-shop derived keys | immediate |
| Cache.sqlite exfil | only known at sift/forensics (files are encrypted) | assume exposed; rotate shop-derived key material; issue all new tokens for that shop; notify per DPDP 48h | 48 h |
| Sync-eavesdrop captures masked ids | detectable log analysis (replays) | rotate anchor; re-issue tokens; treat the link as hostile in future | next sync |
| Template decryption (would require the server master key) | impossible without master key (marked catastrophic, R2), but if it happens | full re-issuance of affected templates + notification | 72 h |
| Operator override abuse | hash-chained audit; anomaly rules at sync | disciplinary + revocation of operator token; re-enrol that operator's biometric access | next sync |

## 7. Residual privacy risk

The only residual risks are: (1) central-authority insider correlation (R2/R5 –
owned by authority HSMs and DP program); (2) physical PAD defeat (R1); (3) a
future A.I.-based re-render that defeats current PAD (R1 — mitigation: PAD is
a live, upgradeable component; model updates are signed and kill-switchable).
Each is accepted with an explicit owner, written down, and re-reviewed
annually or on major model/sensor change.

## 8. Review cadence

PIA is re-run on: new biometric model/sensor, schema change, sync-protocol
change, new PDS entitlement type, or annually — whichever comes first.