# PDSVault — Operator & Support Training

For the shop operator (front line) and the help-desk/SOC agent.  Desk-facing
article; design behavior it references lives in `architecture.md` and the
CLI in `pdsvault verify / diagnostics / pad-report / perf`.

---

## 1. The job in one paragraph

You help a beneficiary get their ration basket when they are **not online**,
using face verification + a secure offline terminal.  The terminal never
calls the network to say *who* you are.  It matches your face against a
signed list, proves you're alive (PAD), checks your basket window, and
records every action it took, signed, so nobody can quietly change it later.

## 2. Shift-start checklist (2 minutes)

1. Boot the device.  Confirm the UI shows **green** (state `OK`).
2. Open `diagnostics`; confirm zero quarantine rows and "ledger intact" and
   "TPM OK".
3. Do one self-test verification with your own face (BPCER check) — if it
   rejects you with a live face, raise an L1 ticket; don't start service on
   a device that can't pass its own PAD.
4. Note whether the last sync is fresh.  If the shop has been offline &gt; 7
   days, tell the supervisor; the device will still serve, but you'll need a
   sync window soon.

## 3. The normal interaction

```
1. Ask the beneficiary to stand in the guide marks, remove mask/glasses that
   cover the eyes, face the camera.
2. The terminal runs liveness + match.  It shows only a masked id plus the
   photo and basket.
3. Confirm the basket aloud; hand over goods; the terminal marks the token
   used (provisional).
4. Nothing you do here needs the network.
```

**Never** tell the beneficiary their full UID or any PII — the terminal never
shows it, and neither should you.

## 4. When verification rejects a real beneficiary

| Reason shown | Do this |
|---|---|
| `pad_reject` | reposition; better light; retry.  If persistent, use the override path **with a second operator**; log it. |
| `match_fail` | check the last-sync age; if stale, sync; if still failing, use 4-eyes override and raise a re-enrolment ticket. |
| `expired` | the basket window is over.  If close to the window end, a grace band may allow one basket — the terminal tells you.  Never extend by hand. |
| `revoked` | the beneficiary is on the signed revocation list.  Do **not** serve.  Explain politely; direct to the authority desk. |
| `duplicate` | this token was already redeemed (possibly at another shop).  Do **not** serve; note the case for the supervisor. |
| `lockout` | too many failures (safety); wait out the budget, then retry legitimately. |

## 5. Four-eyes override — rules

- Requires **two distinct operators**: one to approve, one to witness.
- Requires a signed reason from a fixed list (no free text).
- Hard per-shift budget; when exhausted, the override path closes.
- Overrides are *provisional* — the authority re-checks them at sync and a
  bad override is reversed + charged back.  This is a feature; never cover it
  up; the ledger makes denial impossible anyway.

## 6. Red states — what you must NOT do

| State | Never attempt |
|---|---|
| LEDGER GAP | never edit the ledger by hand; preserve evidence; escalate to L2 |
| SIGNATURE FAIL | never hand-serve the beneficiary; the row is untrusted |
| CLOCK TAMPER | never "fix" the date; rebooting won't help; device must sync/rre-provision |
| TPM FAILURE | never run with TPM bypassed; never "temporarily" accept it |

The rule of thumb: **an amber state may serve after logged override/reason,
red states never serve.**  The device is built to fail closed; your job is to
respect that so the integrity story stays true.

## 7. Disputes & evidence

- Every verification, override, and denial is in the signed ledger with an
  anchor — a beneficiary dispute is settled by an auditor verifying the
  Merkle inclusion proof, **not** by trusting any one device.
- If you're asked to "delete" a record: only a **signed purge instruction**
  from the authority does that, and it produces an erasure receipt.  You
  can't delete rows by hand — and shouldn't need to.

## 8. Help-desk / SOC playbook (condensed)

- Triage from the `diagnostics` output + sync evidence (attestation, ledger
  anchor, clock anchor, quarantine report).
- L1 (amber, single-queue): retry/reboot/ticket → see runbook §3.
- L2 (red, repeated): preserve device + logs, swap unit, SOC.
- L3 (breach suspicion): freeze sync, revoke device key server-side, DPDP
  notify per SOP (runbook §8).

## 9. Certification

Recertify each quarter with a practical test: (1) run an end-to-end
verification; (2) identify all four red states on a training unit;
(3) execute a four-eyes override correctly; (4) explain why an offline device
can't be rolled back to yesterday.