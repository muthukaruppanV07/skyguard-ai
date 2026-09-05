# PDSVault

**Offline, zero-trust Aadhaar face-verification for PDS ration shops.**

A reference implementation of a ration-shop terminal that verifies a
beneficiary's face — **with no network call** — and provisions their
entitlement basket from crypto-authentic local state.  Every device, human,
and byte on the wire is treated as a potential adversary; the system is
designed to **fail closed** on any doubt, and every decision is provably
auditable via a signed Merkle ledger.

This repository is a *runnable slice*: the full security story is specified
in `docs/` (threat model, verification matrix, architecture, PIA, runbook,
training, PAD test plan) and *enforced* by a 79-test suite that includes
fault injection, property tests, fuzzing, and an ISO/IEC 30107-3 PAD rig.

## Why

Aadhaar-backed entitlements need to work where the network does not reach
(two-G coverage holes, market days, floods).  Ration fraud starts at the
shop line — impersonation, double-dipping, cache tampering, clock rewinding,
operator override abuse — so the terminal is built from the assumption that
it is attacked, not that it is trusted.

## What it does

- **Offline verification:** face capture → liveness/PAD → matching → signed
  entitlement window → provisional token redemption.  Zero network calls in
  the local path (asserted by test).
- **Fail-closed integrity:** TPM-sealed keys, PCR-measured app+cache+model,
  monotonic anti-rollback, signed clock anchors, signature-verified records
  rechecked at point of use.
- **Auditable by construction:** append-only Merkle ledger with periodic
  signed anchors; no silent edits; four-eyes operator overrides with limits.
- **Offline double-spend protection:** blinded, epoch-scoped tokens;
  uniqueness decided centrally at sync; duplicate flags + revocation +
  chargeback; local double-spend denied outright.
- **Privacy by design:** no full UID, no PII beyond a masked id and an
  encrypted per-shop template; server master keys never touch the device.
- **Detect, don't trust:** tamper tools ship in the repo (`tools/inject.py`)
  and the faults they produce are the *test suite*.

## Quick start

```bash
python -B -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -e .[dev]
pytest -q                            # 79 tests, must be green
```

Then play with a simulated village:

```bash
python -m pdssec.cli demo --shops 2 --ben 50 --seed 7
python -m pdssec.cli verify --shops 2 --ben 50 --impostor --dir demo
python -m pdssec.cli diagnostics --shops 2 --ben 50 --dir demo
python -m pdssec.cli pad-report
```

Supplying a **wrong/absent seed** or running against a mismatched directory
makes the CLI confess "cache mismatch" rather than trusting the new files —
the secure-clock anchor and poison-detection rules apply to the demo too.

## Project layout

```
src/pdssec/        implementation (crypto, tpm, identity, timekeeper, store,
                   ledger, audit, entitlement, matcher, pad, sync, device,
                   simulator, fuzz, cli)
tests/             79 tests: unit + property + fault-injection + fuzz + PAD
tools/             gen_village.py, inject.py (adversary injectors)
docs/              threat_model · verification_matrix · architecture ·
                   schema · pia · runbook · training · pad_test_plan
```

## Documentation map

| Document | Read it if you want to |
|---|---|
| `docs/threat_model.md` | the adversarial analysis (T1–T14) and residual risk |
| `docs/verification_matrix.md` | threat → mitigation → test → result; the enforcement contract |
| `docs/architecture.md` | the design, trust chain, flows, performance budget |
| `docs/schema.md` | the schema, Merkle ledger, sync format |
| `docs/pia.md` | DPDP Act / UIDAI / ISO 27701 privacy mapping |
| `docs/runbook.md` | field ops, failure matrix, recovery, breach response |
| `docs/training.md` | operator and support training |
| `docs/pad_test_plan.md` | ISO/IEC 30107-3 APCER/BPCER methodology |

## Scope & honesty

This is a security reference and engineering slice, not a shipping product:
- The TPM and PAD sensor are mocked (deterministic) so the suite runs on any
  machine; the final hardware numbers belong in the real-sensor field plan
  (`docs/pad_test_plan.md`, `docs/verification_matrix.md` §7).
- The matcher is a stand-in cosine scorer producing realistic score
  distributions; transport this design to a real Face-Net/ArcFace pipeline.
- Residual risks are documented and owned in `docs/threat_model.md` §6 —
  nothing is silently assumed away.

License: MIT.