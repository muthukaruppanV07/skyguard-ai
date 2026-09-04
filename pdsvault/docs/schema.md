# PDSVault — Schema & Ledger Design

SQLite (WAL mode; SQLCipher page encryption in production) with hash-pinned,
versioned migrations.  **All on-device tables are a cache mirror of
authority-signed records; the canonical bytes a record is signed over are
defined by `crypto.py::canonical`.**

## 1. Canonical serialisation

Every signed entity is `canonical(signed_kind, resource, body, epoch_scope)`:

```
sha256( "PDSVAULT|1|"    ← fixed domain string (version-namespaced)
      | kind             ← e.g. "beneficiary", "token", "revoke"
      | resource         ← e.g. masked uid / dsid / device_id
      | epoch_scope      ← e.g. "epoch:2026-W33"
      | canonical(to_dict(body)) )
```

`canonical` recurses the `dict`: keys sorted, values rendered deterministically
(booleans `true/false`, bytes base64, `None` literal `null`).  **Field order,
whitespace and types are irrelevant to validity** — the schema's `canonical
roundtrip` property test proves re-serialised payloads verify identically.

## 2. On-device tables

### `beneficiaries`

| column | type | derives from | notes |
|---|---|---|---|
| `dsid` | TEXT | masked uid (HKDF-scoped domain), the only id on device | primary key |
| `display_tag` | TEXT | signed body | e.g. masked uid short form for the operator UI |
| `template_enc` | BLOB | AES-GCM under per-shop domain key | never plaintext at rest |
| `template_version` | INT | signed body | model-space pin |
| `signed_body` | TEXT | signed | canonical bytes the signature covers |
| `basket` | TEXT | signed body | canonical entitlement |
| `epoch_from/epoch_to` | INT | signed body | validity window |
| `status` | TEXT | signed body | `active` \| `revoked` |
| `last_used_seq` | INT | local | redemption high-water mark |
| `needs_reenroll` | INT | local | set by template migration |

Enforcement: an unsigned / signature-broken row is quarantined, never
displayed, never matched against (`tests/test_store.py`).

### `tokens`

| column | notes |
|---|---|
| `tok_id`, `dsid`, `basket`, `epoch_from/epoch_to` | signed by authority |
| `used_local` | set on provisional redemption |
| `extras` | signed extras (e.g. grace) |
| `signed_body` | canonical signature coverage |

Local double-spend = a second redemption attempt on `used_local=1` is refused
deterministically; cross-shop duplicates are resolved centrally at sync.

### `revocations`

| column | notes |
|---|---|
| `dsid`, `cache_epoch`, `token_delta` | signed; applied on ingest; point-of-use check |
| `signed_body` | signature is verified before the row exists |

### `sync_state`, `ledger_block`, `ledger_txn`, `quarantined`, `event_log`

Covered in §3–§5 and `docs/ledger` design below; `event_log` is a circular
signed audit buffer (the on-device "everything is logged" guarantee).

### `schema_version`, optional `meta`

Migrations ship as hash-pinned modules; the migration chain's hash is
measured into the PCR bank at boot.  A DB at an unknown `schema_version`
is not opened as trusted (fail closed).

## 3. Ledger (append-only Merkle header-chain)

`block = {index, prev_hash, txn_root, sig, anchor?}`; every `txn` contributes
to the per-block Merkle `txn_root`; every `ANCHOR_EVERY` blocks the authority
signs `anchor_hash = H(chain_head)` again, pinning the whole chain.

- **Append-only by construction:** `event_log` and `ledger_txn` are only ever
  inserted; no update/delete path exists in the on-device schema (asserted by
  `test_ledger::test_ledger_is_append_only_by_construction`).
- **Gap detection:** `next_index != stored.prev_index + 1` → chain broken →
  device blocks further operations (`test_ledger::test_gap_detection`,
  `test_faults::test_ledger_gap_blocks_further_ops`).
- **Tamper detection:** any row edit flips its Merkle path → root mismatch
  (`test_ledger::test_txn_delete_detected_as_root_mismatch`).
- **Auditability:** an inclusion proof + signed anchor lets an external
  auditor verify any past event without trusting the device (`test_ledger::
  test_merkle_inclusion_proof`).

```
 idx prev_hash txn_root                                      anchor
 ────┬─────────┬──────────────────────────────────────────────┬─
   0 │  H(0)   │ root(t0..t9)                                │ A0
   1 │  H(b0)  │ root(t10..t27)                              │
   2 │  H(b1)  │ root(t28..t50)                              │
   3 │  H(b2)  │ root(t51..t63)                              │ A1  ← signed
   4 │  H(b3)  │ root(t64..t80)                              │
  ...
```

## 4. Sync payload format

Push (device → server): evidence only —
`{device_id, attestation_quote, clock_anchor, ledger_anchor, redeemed_tokens,
  verification_log, quarantine_report}`.

Pull (server → device): snapshot —
`{version, seq, prev_snapshot_hash(=prior snapshot seq/hash), merkle_root,
  records[], duplicate_flags[], revocations[], clock_anchor, model_update?,
  kill_switch?, sig}`.

Canonical hashing covers the entire snapshot body; the device re-verifies the
signature, the `prev` linkage and the Merkle root **before** applying
anything (§5 of architecture.md).  Deliveries are chunked at
`CHUNK_RECORDS` records per chunk with per-chunk `SHA-256`, resumable from
`sync_state`, and cross-checked against the snapshot Merkle root, so a torn
or corrupt transfer can never partially apply poisoned state (tested by
`test_sync::test_corrupt_chunk_quarantined_not_applied`).

## 5. Quarantine

Anything that fails its signature, canonical parse, type check, or chunk
hash is moved to `quarantined {payload, reason, when}` — the parse/apply path
never raises and never partially commits.  Quarantine rows count toward the
device's health signal in the next sync (`self_diagnostics()` → quarantine
count) and are visible via the operator CLI / runbook.

## 6. Key storage

| Key | Where it lives |
|---|---|
| authority Ed25519 | server HSM, split custody — **never on device** (public key provisioned) |
| master UID / template keys | server — devices hold only derived, domain/ shop-scoped descendants |
| `storage_key`, `device_attest`, `device_ledger` | TPM-sealed blobs, unsealed at boot, wiped after use |
| sync `sync_state` | plaintext locals only (seq/hashes are not a secret) |

Detailed derivation graphs: `docs/threat_model.md` §7.

## 7. Schema-as-trust story

Because migrations are hash-pinned **and** measured into the PCR bank, an
attacker who re-writes the schema (e.g. strips a NOT NULL, adds a column that
holds unsigned data, rewrites a quarantine function) changes the measured
state and the storage key will not unseal.  The on-disk schema therefore
participates in the device's integrity boundary, not outside it.