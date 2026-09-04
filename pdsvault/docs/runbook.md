# PDSVault — Operations Runbook & Failure Matrix

Companion to `architecture.md` (design) and `threat_model.md` (threats).
This document is what a field operator, a help-desk agent, and the SOC follow.
The reference implementation exposes the equivalent steps as the `pdsvault`
CLI (`verify`, `diagnostics`, `pad-report`, `inject`, `perf`).

---

## 1. Equipment & expected states

| State | Meaning | Can it verify faces? | Operators see |
|---|---|---|---|
| `OK` | boot self-diagnostics pass; ledger intact; TPM unsealed; clock anchored; quarantine empty | yes | green in UI |
| `DEGRADED` | some items red but no integrity loss (e.g. quarantine has rows; PAD sensor re-calibration pending) | yes (if no integrity red) | amber; runbook §3 |
| `TAMPER` | ledger gap, cache signature failure, TPM refusal, clock tamper, schema mismatch | **no** | red; immutable placard; escalate immediately |
| `OFFLINE-LOCKED` | usable offline, not yet synced (normal) | yes | normal; sync pending bar |

Expected behaviour after power loss: the device cold-boots, self-diagnostics
re-run, and it returns to `OK` **if and only if** the ledger is intact and the
TPM unseals under the unchanged PCR policy.  A torn write at shutdown must
never look like a watermark — the WAL + append-only ledger guarantee this
(test: `test_faults::test_disk_full_fails_closed`).

## 2. Boot self-diagnostics

Runs automatically on every boot and on the `diagnostics` CLI verb:

1. TPM presence + PCR measurement + storage-key unseal + attestation test.
2. Ledger: block continuity (no gaps), periodic anchor verification.
3. Cache signature scan (sampled or full at shift start).
4. Schema version + migration hash vs measured PCR.
5. Quarantine count and reasons.
6. Secure clock: last anchor, monotonic direction, wall-clock drift.
7. Disk space headroom.

Output: one of the states in §1.  Any `TAMPER` item freezes the entitlement
UI; the freeze is itself logged and won't clear until the underlying
condition is remedied.

## 3. Failure matrix

| Symptom | Likely cause | Operator action | Escalate if |
|---|---|---|---|
| UI stuck on "camera initialising" | camera focus/IR fault, driver | reboot; clean lens; re-seat USB | persists 2 reboots (hardware) |
| Face not enrolled "match_fail" for a valid beneficiary | long time since last sync; stale cache | check sync age; do a sync; if still fail, use 4-eyes override path | 3rd occurrence — authority re-enrolment |
| PAD rejects a visible live face (BPCER) | lighting/angle; PAD false-reject | reposition beneficiary; retry; if persistent, 4-eyes + log | PAD sensor re-calibration ticket |
| "ledger gap" freeze | prior crisis, torn cache, tamper | **do not** clear by hand; preserve evidence; offline evidence preserved for the SOC | always — device is in TAMPER |
| "signature verification failed" on a row | corrupted or tampered row | captured to quarantine automatically; device marks just that row, doesn't freeze | paranoid check — quarantine count grows |
| "time sync failed / clock tamper" | anchor missing / counter mismatch | do a sync; if anchor is bad, swap device | always — fail closed |
| "TPM failure" at boot | TPM absent / reflash / counterfeit / battery | if TPM absent, device is a brick (by design) | always — replace unit |
| Quarantine count climbing | poisoned chunks / hostile feed | sync again; chunks re-fetch; keep device on the fence | count &gt; threshold → integrity alarm |
| Sync never completes over EDGE | bad signal, large chunk backlog | use resumable chunks; retry in a better-window; phys-sync via USB-serial as fallback | backlog &gt; 1 week → ops review |
| Override budget exhausted | operator abusing four-eyes | ID is locked; re-enrolment requires authority reset | always — audit at next sync |

## 4. Recovery procedures

1. **Recover from a torn / partial sync** — simply re-sync; the client holds
   `(seq, hash)` and resumes; uncommitted chunks are re-fetched
   (`test_faults::test_partial_sync_retains_consistency`).
2. **Recover from a quarantine storm** — sync, then re-sync; if chunks keep
   failing, run `diagnostics`, then swap the device; preserve the SQLite file
   for forensics (never "fix it in place").
3. **Rebuild a confiscated device** — boot to a signed minimal image; the
   image hashes restore the correct PCR; re-provision the shop-scoped keys
   from the authority; a fresh sync repopulates the cache from the signed
   snapshot.
4. **Erasure / purge (right to be forgotten)** — the next snapshot carries a
   signed purge instruction; the device deletes the row, records a deletion
   receipt, and returns a signed "no rows for DSID" statement on the following
   sync.

## 5. Unsafe operations (never do)

- Never resolve a ledger gap by hand-editing `ledger_block`.
- Never clear quarantine by deleting rows — it is evidence.
- Never copy a cache.sqlite between devices or shops.
- Never "borrow" a device from shop A to serve shop B.
- Never accept a firmware/OS update that isn't signature-verified by the
  signed update chain.
- Never run the device with TPM failure "temporarily".

## 6. Clock & time

- Secure time = signed anchors (authority) + monotonic counter (TPM NV).
- A backward jump &gt; `CLOCK_TOLERANCE` or an excessive forward jump
  triggers a tamper event and disables entitlement until remedied.
- Per-device drift is smoothed from anchor deltas and reported in sync
  evidence (SOC can see drift per shop).

## 7. Monitoring & budget (local + remote)

**Local (no network needed):**
- last N thousand operator events in `event_log` (circular, signed).
- `diagnostics` verb prints state, quarantine count, ledger health, clock.

**Remote (at next sync):**
- attestation quote, ledger anchor, clock anchor, quarantine report.
- duplicate flags + chargeback list; anomaly rules (override rate, FRR spikes,
  same-dsid-across-shops).

## 8. Breach response (DPDP 30/48/72h cadence)

1. **Detect:** tamper flags, attestation failure, quarantine storm, anomaly
   rule hit — each is an incident, not a curiosity.
2. **Contain:** fail-closed device is already contained; freeze the sync
   channel; revoke the shop's device key server-side.
3. **Assess:** pull evidence bundle (sync evidence + engineering log).
4. **Notify:** per DPDP breach rules and the state PDS SOP.
5. **Eradicate:** rotate shop-derived keys, re-issue tokens for affected
   beneficiaries, re-provision or retire the device.
6. **Recover:** re-image, re-provision, re-sync; run self-diagnostics to
   return to `OK`.

## 9. Escalation playbook

| Tier | Condition | Action |
|---|---|---|
| L1 | UI amber, single-queue issue | retry; reboot; ticket |
| L2 | TAMPER flags, quarantine storm, repeat failures | preserve evidence; swap device; SOC involvement |
| L3 | suspected intrusion / key compromise / breach | freeze sync; revoke device key; DPDP notify; full PIA re-run |