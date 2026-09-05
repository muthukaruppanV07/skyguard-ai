# PDSVault — Threat Model

**Single source of truth for the adversarial analysis.**  `verification_matrix.md`
tracks which threats are enforced (and by which test); `architecture.md` describes
the design; `runbook.md` covers operations.  If a threat changes, this file
changes first.

Version 0.1.0 · DREAD + STRIDE walkthrough · risk owner: security/architecture.

---

## 1. Scope & assumptions

- **In scope:** the offline shop terminal, its local cache + TPM, the sync
  protocol, the entitlement/basket decision, the PAD/biometric pipeline, the
  operator UI/override paths, the on-device ledger, and the trigger / kill-switch
  trusted-update path.
- **Out of scope (owned elsewhere):** central authority server infrastructure,
  key custody at the authority (HSM procedures), physical site security
  (guards/CCTV), the final retail supply chain, and the transport network
  operator (2G/EDGE carrier).  These are "owned, not hidden" residual risks (§6).
- **Adversary capabilities assumed:** offline or online access to a shop device
  (physical possession of the unenrolled, unlocked terminal is NOT granted by
  this document — that device is treated as attacked and fails closed);
  the ability to run arbitrary code inside a *software-only* image on the same
  CPU; the ability to dump operator RAM / cache.sqlite from a seized device;
  the ability to stage presentation attacks (printed photo, mobile video, masks);
  the ability to replay, poison, truncate, or reorder network traffic;
  the ability to forge templates *if and only if* they also hold authority keys.
- **Threat owner discipline:** every threat has an owner (default: pdsvault
  arch) and a disposition: `mitigate` (enforced in reference impl), `transfer`
  (certification / HSM), `accept` (documented residual), or `polish` (protocol
  hardened later, mechanism shown).

### Assets to protect

| Asset | Scale of loss (worst case) |
|---|---|
| A1. Basket/token integrity — a beneficiary can't be impersonated to drain quota/subsidy | per-beneficiary quota + cash-equivalent, large cohort |
| A2. Biometric templates + masked ids at rest | identity-level data, ε thousands to lakhs of persons |
| A3. Device operational trust — a terminal that *believes* it is honest when it isn't | all beneficiaries served by that shop |
| A4. Verifiable audit trail for disputes | legal/PDS compliance exposure |
| A5. The offline-first guarantee — no requirement to reach the network to serve | availability in rural/2G coverage holes |

## 2. STRIDE walkthrough (interactive surface)

| Category | Example in scope | Disposition |
|---|---|---|
| **Spoofing** | attacker presents a photo/video/mask to the camera, or ships a counterfeit TPM quote | mitigate (PAD + attestation) |
| **Tampering** | edit cache.sqlite, reorder/truncate ledger, reflash firmware, rewrite the schema | mitigate (signed records, Merkle chain, PCR-measured cache) |
| **Repudiation** | operator overrides a basket and denies it | mitigate (signed four-eyes log, hash-chained) |
| **Information disclosure** | dump SIM-cache, scanned templates, cross-shop correlation | mitigate (masking, domain keys, encryption-sealed) |
| **Denial of service** | queue flooding, disk-full at a dup, poisoned chunk loop | mitigate (fail-closed, quarantine, resumable chunks) |
| **Elevation** | a captured device being *upgraded* into a device that believes it's fresh (re-enrolment theft) | mitigate (PCR-12 chain, monotonic NV counter, signed re-enrolment) |

## 3. Threats (T1–T14), mitigations, and the tests that hold them

### Identity & biometrics

| ID | Threat | Impact | Mitigation | Disposition |
|---|---|---|---|---|
| T1 | **Impersonation via synthetic/duplicate face** — attacker embeds a copy of the target's biometrics, or synthesizes a face; "same person, twice" fraud | quota drain, impersonation | masked uid plus per-shop blinding prevents "same id across shops"; PAD + threshold operating point (FAR) bind the biometric gate | mitigate |
| T2 | **Deepfake at capture** — real-time re-render of a victim's face | same as T1, higher quality | PAD with depth/IR/challenge reprocessing; operator UI shows the *live* frame, not just the matched embed | mitigate |
| T3 | **Cache/eavesdrop replay** — steal stored templates + masked ids and replay a *stored* verification so the device thinks a live face matched | full impersonation with no attacker present | templates are AES-GCM-encrypted under a TPM-sealed per-shop key and domain-scoped; masked ids are HKDF-scoped per shop; even a full dump is not enough — replaying a stored *verification* is impossible because the device re-derives the match from live capture, not from persisted "was-matched" state | mitigate |
| T4 | **Match-bypass** — algorithmic exploit of the matcher (e.g. adversarial perturbation) | single-id fraud | cosine distance at FAR=1e-4; 1:N amplification handled via per-comparison threshold; adversarial robustness testing is in the matcher acceptance suite | mitigate (partial: adversarial-neural-certification is follow-up) |
| T5 | **Presentation attack (printed photo / video replay / 3D mask / paper cutout)** | the flagship vector | ISO 30107-3 PAD: sensor fusion — IR + depth + liveness challenge + HW countermeasures; rigor measured as APCER/BPCER (see `docs/pad_test_plan.md`) | mitigate |
| T6 | **Template poisoning** — attacker with brief device access writes a *matched* template for their own vector | one-id fraud until re-enrolment | template records are authority-signed; unsigned or signature-broken rows are quarantined (never matched); template_version pins the model; needs_reenroll separates spaces | mitigate |

### Device & key compromise

| ID | Threat | Impact | Mitigation | Disposition |
|---|---|---|---|---|
| T7 | **Seized device → key extraction** — physical RAM/dump attacks | decrypt everything on that shop | storage key is a TPM-sealed blob sealed to PCR policy + SRK; keys exist in RAM only transiently, wiped after use; persisted key material is the sealed blob only | mitigate |
| T8 | **Reflash / rollback / counterfeit TPM** — attacker re-flashes an old signed OS, or a software TPM, to reset counters or weaken policy | a "fresh" forged device | PCR-12 measurement chain; TPM2 monotonic NV counter gates firmware **and** snapshot generations (anti-rollback); TPM attestation quote is signed by a device key that a forged TPM cannot reproduce; on any doubt the device fails closed | mitigate |
| T9 | **Clock rewinding** — roll the clock back weeks to revive stale entitlement windows | stale baskets made live again | secure time = signed anchors + monotonic local counter; backward jump → tamper event + verification disabled + quarantine of sync; entitlement requires both a valid window and a live anchor | mitigate |
| T10 | **Offline cache poisoning** — attacker edits the cache directly while the device is offline | serve fake/forged baskets | every record is authority-signed over a canonical body; device derives **all** persisted fields from the signed body; point-of-use re-verification; anything absent/malformed is quarantined | mitigate |
| T11 | **Database tamper / token reuse** | double-dip a basket, forge redemption log | append-only Merkle ledger with periodic signed root anchors; gap detection freezes ops; any edited row is detected; local token double-spend denied deterministically | mitigate |
| T12 | **Operator misuse / un-audited override** | fake overrides drain quota | signed operator log (event_log) hash-chained into the ledger; four-eyes override requires 2 distinct operators, signed reason, per-shift rate limits, provisional status with server-side audit | mitigate |
| T13 | **Data-at-rest theft / egress exfil** | templates, mask ids, basket history | encryption at rest; no PII beyond mask; per-shop domain keys; differential privacy on any aggregate that leaves the device | mitigate (privacy), transfer (EAL/HSM at authority) |

### Network & sync

| ID | Threat | Impact | Mitigation | Disposition |
|---|---|---|---|---|
| T14 | **Poisoned / replayed / stale snapshot** — attacker feeds a bad `sync` answer (signed by *their* key) or a replayed old snapshot | device applies wrong beneficiary/balance state, or revives old windows | snapshots are authority-signed, versioned, `prev`-chained, and Merkle-rooted over records; device validates signature + linkage + root before applying; replayed old seq rejected; corrupt chunks quarantined; stale epochs expire locally | mitigate |

## 4. Decision & key-derivation graphs

### 4.1 Key derivation (server side)

```
master_secret (server HSM, NEVEr on device)
 ├─ HKDF("uid")   → uid_priv
 ├─ HKDF("mask")  → mask_key        → masked_uid = HMAC(mask_key, uid) (per-UID, constant)
 ├─ HKDF("template")→ template_master ↓ per-shop HKDF(template_master, shop_ds)
 └─ HKDF("token") → token_master    → per-cycle blinded token ids
```

### 4.2 What the device actually holds

```
device_keys (TPM-sealed)
 ├─ device_attest   (quote signer)
 └─ device_ledger   (block header signer)
provisioned-public: authority_pub, clock_anchor_pub (if separate), mask_key_derived(shop)

cache.sqlite (SQLCipher, key = TPM-sealed storage_key)
 ├─ dsids (masked, shop-scoped)
 ├─ template_enc (AES-GCM under per-shop derived key)
 └─ tokens / revocations / ledger / events (signed bodies)
```

No device ever holds: full UIDs, template_master, token_master, authority
private key.  Re-derivation is impossible from a single shop dump; even the
mask on one shop is useless in another because it is domain-scoped.

### 4.3 Decision flow (fail-closed chain)

```
live (PAD)          ──no──► deny(pad)
   │ yes
match ≥ threshold   ──no──► deny(match)
   │ yes
basket window valid ──no──► deny(expired)      [signed epoch validity]
   │ yes
beneficiary active  ──no──► deny(revoked)      [signed revocation]
   │ yes
token non-spent     ──no──► deny(duplicate)    [local + central]
   │ yes
signed ledger row   ──no──► TAMPER / quarantine (the failure itself is logged)
   │ yes ──► redeem (provisional, masked only) ──► operator UI shows mask+photo+basket
```

Every denial reason is recorded as a signed ledger event; nothing is decided
locally that isn't re-decidable from the signed inputs.  This chain is
implemented by `EntitlementEngine` in `tests/test_entitlement.py`.

## 5. Attack scenarios

| Scenario | Step-by-step attacker plan | Defeated by |
|---|---|---|
| S1. Street mugging of a phone/tablet | 1) yank the terminal 2) dump RAM + cache.sqlite 3) reflash an old signed OS to reopen counters 4) replay a stolen "fresh" device | TPM-sealed keys: the dump is AES ciphertext; reflash changes PCR measurement so the sealed key never unseals; NV counter cannot regress; forged TPM can't sign a valid quote |
| S2. Inside the shop line (operator collusion) | operator lets a non-beneficiary through the face gate by walking them through "PAD" 0 times | PAD: the gate is not operator-shortable; operator actions are in the signed audit log; 4-eyes + limits stop quota farming; authority audit at sync reveals anomalies |
| S3. Offline double-dip across villages | friend A redeems token T at shop A; friend B redeems same T at shop B before either syncs | uniqueness is central: second sync flags duplicate_tokens, follows with signed revocation + chargeback; local second use of an already-used token is denied outright |
| S4. Network attacker between shop and server | reorder/poison/truncate the sync stream | signed snapshots with prev-chaining and Merkle roots: a poisoned or replayed snapshot never applies; torn chunks get quarantined and re-fetched |
| S5. Stale-window revival | roll clock back to "yesterday" when a basket window was still open | signed anchors + monotonic counter: backward jump = tamper event + fail-closed; and epoch `valid_to` needn't even be trusted locally — the live clock anchor is re-verified at every entitlement decision |
| S6. Fake TPM / software-only device | run an emulated TPM that reports a clean PCR and a valid quote for a compromised image | the quote signature is created by a key that lives **inside** the sealed TPM; a software emulator can't produce it.  Reference mock: `MockTPM` vs `FakeTPMForge` — the forge is detected by quote verification (tested) |
| S7. Quota farming via overrides | operator files 4-eyes override 50×/day for cronies | rate limits per-shift + signed reason + authoritative audit at sync; the log is hash-chained so the sequence is undeniable |
| S8. Cache poisoning with a *plausible* false record | attacker crafts a beneficiary row with a *valid-looking* signature from an old leak or their own key | signatures verify against the authority public key — not any key; an old leaked key would have been revoked in the snapshot; the device never accepts unsigned state |

## 6. Residual risk (owned, accepted, or transferred)

|#| Residual | Disposition | Owner | Notes |
|---|---|---|---|---|
| R1 | Physical PAD defeat by an IR-grade live-face hardware attacker | accepted (research-phase; final sensor re-characterised at field procurement) | PAD eng | APCER/BPCER re-measured on the actual sensor before production sign-off |
| R2 | Central-authority compromise (key custody, insider DB access) | transferred | authority HSM team | split custody, FIPS/CC-certified HSM; device-side design already ensures keys never live on-device |
| R3 | Hardware side-channel against a real TPM (micro-architecture) | transferred | hardware cert | CC EAL4+ / FIPS 140-3 Level 2+ requirement in the BOM |
| R4 | DoS of a queue / shop availability | accepted | ops | physical queue policy; fail-closed protects integrity, not uptime |
| R5 | Cross-shop reidentification via central-data correlation | accepted | authority DP | masked-id HKDF scope + differential privacy on egress aggregates; full PIA in `docs/pia.md` |
| R6 | Adversarial-neural certification of the matcher (T4 deep) | polish (mechanism defined; certification is follow-up) | ML eng | robustness tests in matcher acceptance suite; formal certification deferred |

Cost/benefit discipline: PAD + TPM sealing + camouflage-free masking are
cheap (a few thousand per unit, see architecture §9) and eliminate T1, T2,
T5, T7, T8, T13 at the source; every mitigation ships with a green test in
the reference implementation (verification_matrix), so "baked in" is a
matter of record, not assertion.

## 7. How to update this model

1. Add/change a row in §3 (keep T-numbering stable; add T15+ with a date).
2. If a mitigation disappears or weakens, update `disposition` and
   `verification_matrix.md` before anything else ships.
3. Re-run the regression gate (`pytest tests -q`); a matrix row marked ✔
   must be backed by a green test.