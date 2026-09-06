# SPDX-License-Identifier: MIT
"""Identity handling: provisioning, masking, domain separation.

The device is provisioned with *domain keys only* (derived on the authority
side from master keys that never leave the authority).  It never holds:

  * the full Aadhaar UID as a searchable value,
  * the authority master keys,
  * PII beyond (masked_uid, template, entitlement).

Masked UIDs and encrypted templates are stored with a *domain-scoped id*
(DSID) so that two shops seeing the same beneficiary cannot even agree on a
common identifier - cache theft from one shop is useless against another.
"""

from __future__ import annotations

import json

from . import crypto
from .crypto import b64d, b64e


class ProvisioningError(Exception):
    pass


class DomainKeys:
    """Per-shop key material derived from authority master keys."""

    def __init__(self, shop_domain: str, domain_uid_key: bytes,
                 domain_tpl_key: bytes):
        self.shop_domain = shop_domain
        self.domain_uid_key = domain_uid_key
        self.domain_tpl_key = domain_tpl_key

    def mask(self, full_uid: str) -> str:
        return crypto.masked_uid(self.domain_uid_key, full_uid)

    def dsid(self, masked_uid: str) -> str:
        """Domain-scoped identifier: stable within a shop, meaningless across
        shops because both the key and the shop salt differ."""
        return crypto.hmac_sha256(
            self.domain_uid_key,
            (self.shop_domain + "|" + masked_uid).encode(),
        ).hex()[:20]

    def encrypt_template(self, template: bytes) -> str:
        blob = crypto.aead_encrypt(self.domain_tpl_key, template,
                                   aad=self.shop_domain.encode())
        return b64e(blob)

    def decrypt_template(self, ciphertext: str) -> bytes:
        return crypto.aead_decrypt(self.domain_tpl_key, b64d(ciphertext),
                                   aad=self.shop_domain.encode())


def derive_domain_keys(
    master_uid_key: bytes,
    master_template_key: bytes,
    shop_domain: str,
) -> DomainKeys:
    """Authority-side derivation invoked once at provisioning / re-provisioning."""
    return DomainKeys(
        shop_domain=shop_domain,
        domain_uid_key=crypto.domain_uid_key(master_uid_key, shop_domain.encode()),
        domain_tpl_key=crypto.domain_template_key(
            master_template_key, shop_domain.encode()
        ),
    )


# --------------------------------------------------------------------------- #
# Authority identity & provisioning certificate
# --------------------------------------------------------------------------- #

class Authority:
    """Central authority: holds master keys; signs beneficiary records,
    entitlement tokens, sync snapshots, model updates, revocation lists."""

    def __init__(self, master_uid_key: bytes, master_template_key: bytes,
                 epoch_master_key: bytes, signing_sk: bytes):
        self.master_uid_key = master_uid_key
        self.master_template_key = master_template_key
        self.epoch_master_key = epoch_master_key
        self.signing_sk = crypto.load_priv(signing_sk)

    @property
    def signing_pk_der(self) -> bytes:
        return crypto.ed25519_sk_to_pk(self.signing_sk).public_bytes_raw()

    def domain_keys(self, shop_domain: str) -> DomainKeys:
        return derive_domain_keys(self.master_uid_key, self.master_template_key,
                                  shop_domain)

    def sign_beneficiary_record(self, record: dict) -> dict:
        """Sign the canonical payload of a beneficiary record so a poisoned or
        stale cache is cryptographically detectable; no unsigned record is
        ever trusted."""
        body = crypto.canonical(record)
        rec = dict(record)
        rec["body"] = b64e(body)
        rec["sig"] = b64e(crypto.ed25519_sign(self.signing_sk, body))
        return rec

    @classmethod
    def generate(cls, seed: bytes | None = None) -> "Authority":
        if seed is not None:
            def mk(info: bytes) -> bytes:
                return crypto.hkdf(seed, salt=b"pdsvault-master", info=info)
            uid_key = mk(b"uid-key")
            tpl_key = mk(b"tpl-key")
            epoch_key = mk(b"epoch-key")
            signing = crypto.gen_ed25519()
        else:
            uid_key = crypto.rand(32)
            tpl_key = crypto.rand(32)
            epoch_key = crypto.rand(32)
            signing = crypto.gen_ed25519()
        return cls(uid_key, tpl_key, epoch_key,
                   signing.private_bytes_raw())


# --------------------------------------------------------------------------- #
# Verification of authority signatures (device side)
# --------------------------------------------------------------------------- #

def verify_authority_record(authority_pk_der: bytes, rec: dict) -> bool:
    if "body" not in rec or "sig" not in rec:
        return False
    return crypto.ed25519_verify(
        crypto.load_pub(authority_pk_der), b64d(rec["body"]), b64d(rec["sig"])
    )
