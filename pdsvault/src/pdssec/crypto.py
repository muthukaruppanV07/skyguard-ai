# SPDX-License-Identifier: MIT
"""Core cryptographic primitives for PDSVault.

Everything here is symmetric-free-of-secrets-on-device except the storage key,
which is sealed to the TPM/SE (see tpm.py).  Authority-side master keys never
reach the device; the device only ever holds:

  * a per-shop *domain template key*  derived from the authority master key
    (domain separation: cache theft from one shop leaks nothing about another),
  * an HMAC *domain UID key* for masked/pseudonymous identity derivation,
  * device keys sealed to the TPM (sync, ledger, attestation).

Primitives used: Ed25519 (authority/device signatures), AES-256-GCM (sealed
blobs + at-rest column encryption), HKDF-SHA256 (key derivation), HMAC-SHA256
(masking, token checksums).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# --------------------------------------------------------------------------- #
# constants / formats
# --------------------------------------------------------------------------- #

MASKED_UID_LEN = 16          # bytes; 128 bits of HMAC-SHA256 output, truncated
TOKEN_ID_LEN = 32            # bytes; random entitlement token id
NONCE_LEN = 12               # AES-GCM nonce
SIG_ALGO = "ed25519"
AEAD_ALGO = "aes-256-gcm"

# Contexts keep domain separation inside the KDF; never reuse a context.
CTX_MASK = b"pdsvault/uid-mask/v1"
CTX_DOMAIN_TPL = b"pdsvault/domain-template/v1"
CTX_DOMAIN_UID = b"pdsvault/domain-uid/v1"
CTX_EPOCH_BIND = b"pdsvault/epoch-bind/v1"
CTX_STORAGE = b"pdsvault/storage/v1"
CTX_LEDGER = b"pdsvault/ledger/v1"
CTX_SYNC = b"pdsvault/sync/v1"


def rand(n: int) -> bytes:
    return os.urandom(n)


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode("ascii"))


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def hmac_compare(key: bytes, data: bytes, tag: bytes) -> bool:
    return hmac.compare_digest(hmac_sha256(key, data), tag)


# --------------------------------------------------------------------------- #
# Ed25519 signatures
# --------------------------------------------------------------------------- #


def gen_ed25519() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def ed25519_sk_to_pk(sk: Ed25519PrivateKey) -> Ed25519PublicKey:
    return sk.public_key()


def ed25519_sign(sk: Ed25519PrivateKey, message: bytes) -> bytes:
    return sk.sign(message)


def ed25519_verify(pk: Ed25519PublicKey, message: bytes, sig: bytes) -> bool:
    try:
        pk.verify(sig, message)
        return True
    except Exception:
        return False


def load_pub(pub_der: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(pub_der)


def load_priv(priv_der: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(priv_der)


# --------------------------------------------------------------------------- #
# AEAD sealing
# --------------------------------------------------------------------------- #


def aead_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """AES-256-GCM.  Output = nonce || ciphertext || tag."""
    nonce = rand(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce + ct


def aead_decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    if len(blob) < NONCE_LEN + 16:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:NONCE_LEN], blob[NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ct, aad)


# --------------------------------------------------------------------------- #
# KDF
# --------------------------------------------------------------------------- #


def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    ).derive(ikm)


# --------------------------------------------------------------------------- #
# Masking / pseudonymity
# --------------------------------------------------------------------------- #

def masked_uid(domain_uid_key: bytes, full_aadhaar_uid: str) -> str:
    """128-bit domain-scoped pseudonym.  Cannot be reversed without the
    authority master key; identical UID at a different shop yields a different
    mask, so cross-shop correlation of cache contents is impossible."""
    raw = hmac_sha256(domain_uid_key, full_aadhaar_uid.encode("utf-8"))[:MASKED_UID_LEN]
    return b64e(raw)


def domain_template_key(master_template_key: bytes, shop_domain: bytes) -> bytes:
    return hkdf(master_template_key, salt=CTX_DOMAIN_TPL, info=shop_domain)


def domain_uid_key(master_uid_key: bytes, shop_domain: bytes) -> bytes:
    return hkdf(master_uid_key, salt=CTX_DOMAIN_UID, info=shop_domain)


def epoch_binding_key(master_key: bytes, cycle_epoch: int) -> bytes:
    """Key that binds entitlement tokens to a specific cycle epoch, so a token
    minted for cycle N can never be spent in cycle N-1 (anti-replay)."""
    return hkdf(master_key, salt=CTX_EPOCH_BIND, info=str(cycle_epoch).encode())


# --------------------------------------------------------------------------- #
# Entitlement tokens (blinded, authority-signed)
# --------------------------------------------------------------------------- #

def mint_token(
    authority_sk: Ed25519PrivateKey,
    domain_masked_uid: str,
    cycle_epoch: int,
    basket: str,
    valid_from: int,
    valid_to: int,
    token_id: bytes | None = None,
) -> dict:
    """Mint an entitlement token.

    The token carries a *random* token_id (never the UID), an epoch-bound
    basket, and validity window, all signed by the authority.  A shop can
    verify validity locally (signature + epoch clock) and provisionally redeem
    it offline, but cannot tell whether a second shop already redeemed the
    same token: uniqueness is enforced only by the central authority at
    redemption time when the signed record returns in a sync payload.
    """
    token_id = token_id or rand(TOKEN_ID_LEN)
    payload = (
        b"tok/v1"
        + b"|" + token_id
        + b"|" + domain_masked_uid.encode()
        + b"|" + str(cycle_epoch).encode()
        + b"|" + basket.encode()
        + b"|" + str(valid_from).encode()
        + b"|" + str(valid_to).encode()
    )
    sig = ed25519_sign(authority_sk, payload)
    return {
        "token_id": b64e(token_id),
        "masked_uid": domain_masked_uid,
        "cycle_epoch": cycle_epoch,
        "basket": basket,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "payload": b64e(payload),
        "sig": b64e(sig),
    }


def token_payload_bytes(token: dict) -> bytes:
    return b64d(token["payload"])


def verify_token(authority_pk: Ed25519PublicKey, token: dict) -> bool:
    return ed25519_verify(authority_pk, token_payload_bytes(token), b64d(token["sig"]))


# --------------------------------------------------------------------------- #
# Canonical signed record format shared by beneficiary records and sync
# snapshots.  Serialisation must be canonical so signatures are stable.
# --------------------------------------------------------------------------- #

def canonical(obj: dict) -> bytes:
    """Deterministic serialisation: sorted keys, utf-8, ints as decimal."""
    parts = []
    for k in sorted(obj.keys()):
        v = obj[k]
        if isinstance(v, dict):
            v = canonical(v)
        elif isinstance(v, bytes):
            v = b64e(v)
        elif isinstance(v, bool):
            v = "1" if v else "0"
        elif isinstance(v, (int, float)):
            v = repr(v)
        elif v is None:
            v = "null"
        else:
            v = str(v)
        if isinstance(v, bytes):
            v = b64e(v)
        parts.append(str(k) + "=" + v)
    return b"&".join(p.encode("utf-8") for p in parts)


def _parse_canonical(body: bytes) -> dict:
    """Parse canonical serialisation (inverse of `canonical`).  Values are
    strings; caller casts to int/float as needed.  Malformed input raises."""
    if not isinstance(body, (bytes, bytearray)):
        body = body.encode("utf-8")
    out: dict[str, str] = {}
    for part in body.split(b"&"):
        if b"=" not in part:
            raise ValueError("malformed canonical field")
        kb, vb = part.split(b"=", 1)
        try:
            k = kb.decode("utf-8")
            v = vb.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("non-utf8 canonical field")
        if k == "" or k in out:
            raise ValueError("duplicate or empty canonical key")
        out[k] = v
    return out
