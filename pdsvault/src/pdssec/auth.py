# SPDX-License-Identifier: MIT
"""Authority-side operations: beneficiary snapshots, revocation lists,
model-update signing, kill-switch, and sync snapshot construction.

Everything produced here is signed with the authority Ed25519 key.  Devices
only ever *verify* these objects; they never mint anything.
"""

from __future__ import annotations

from . import crypto
from .crypto import b64d, b64e
from .identity import Authority, verify_authority_record


def build_beneficiary_record(
    authority: Authority,
    shop_domain: str,
    full_uid: str,
    template: bytes,
    basket: str,
    valid_from: int,
    valid_to: int,
    cycle_epoch: int,
    pin: str | None = None,
) -> dict:
    """Build + sign a beneficiary record for one shop domain.

    The record carries only the *masked* uid and an AEAD-encrypted template
    (encrypted under this shop's domain template key), so a copy of this row
    on any other device or any cached leak exposes no usable biometric.

    `pin` (optional) provisions the offline PIN fallback; only its PBKDF2
    hash+salt enter the *signed* record so it cannot be tampered with without
    breaking the authority signature.
    """
    dk = authority.domain_keys(shop_domain)
    masked = dk.mask(full_uid)
    record = {
        "masked_uid": masked,
        "template_enc": dk.encrypt_template(template),
        "entitlements": basket,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "cycle_epoch": cycle_epoch,
    }
    if pin is not None:
        from .bio import PinVerifier
        salt = crypto.rand(16)
        record["pin_salt"] = b64e(salt)
        record["pin_hash"] = b64e(PinVerifier().hash_pin(pin, salt))
    return authority.sign_beneficiary_record(record)


def build_revocation(authority: Authority, masked_uid: str,
                     reason: str, valid_from: int, valid_to: int) -> dict:
    """Revocation bound to a *masked* uid so a device can resolve its DSID
    and apply it without ever seeing the full UID."""
    return authority.sign_beneficiary_record({
        "kind": "revocation",
        "masked_uid": masked_uid,
        "reason": reason,
        "valid_from": valid_from,
        "valid_to": valid_to,
    })


def build_kill_switch(authority: Authority, model_version: str) -> dict:
    """Signed kill-switch: ordering a device to stop serving a model version."""
    return authority.sign_beneficiary_record({
        "kind": "kill_switch",
        "model_version": model_version,
    })


def build_model_update(authority: Authority, model_version: str,
                       model_sha256: str, staged: bool = True) -> dict:
    return authority.sign_beneficiary_record({
        "kind": "model_update",
        "model_version": model_version,
        "model_sha256": model_sha256,
        "staged": staged,
    })


def build_clock_anchor(authority: Authority, unix_ts: int,
                       device_domain: str) -> dict:
    body = crypto.canonical({"unix": unix_ts, "device_domain": device_domain})
    return {"body": b64e(body),
            "sig": b64e(crypto.ed25519_sign(authority.signing_sk, body))}


# --------------------------------------------------------------------------- #
# Snapshot / sync payloads
# --------------------------------------------------------------------------- #

def build_snapshot(authority: Authority, records: list[dict],
                   snapshot_seq: int, prev_snapshot_hash: str) -> dict:
    """Authority-signed snapshot of the beneficiary set for one domain.

    `prev_snapshot_hash` links snapshots so a device can detect a poisoned or
    replayed snapshot even if it was served by a hostile middlebox.
    """
    leaves = sorted(crypto.canonical(r) for r in records)
    from .ledger import MerkleTree
    roots = MerkleTree([crypto.sha256(l) for l in leaves]).root
    snap = {
        "seq": snapshot_seq,
        "prev_snapshot_hash": prev_snapshot_hash,
        "merkle_root": b64e(roots),
        "n": len(records),
    }
    return authority.sign_beneficiary_record(snap)
