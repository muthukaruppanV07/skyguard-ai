# SPDX-License-Identifier: MIT
"""Unit tests: crypto primitives, masking, tokens, TPM sealing,
canonical round-trips, and the failure-closed behaviour of the mock TPM."""

from __future__ import annotations

import os

import pytest

from pdssec import crypto
from pdssec import tpm as tpmm
from pdssec.identity import Authority


def test_ed25519_roundtrip():
    sk = crypto.gen_ed25519()
    msg = crypto.rand(100)
    sig = crypto.ed25519_sign(sk, msg)
    pk = crypto.ed25519_sk_to_pk(sk)
    assert crypto.ed25519_verify(pk, msg, sig)
    assert not crypto.ed25519_verify(pk, msg + b"x", sig)
    assert not crypto.ed25519_verify(crypto.gen_ed25519().public_key(),
                                     msg, sig)


def test_aead_roundtrip_and_tamper():
    key = crypto.rand(32)
    pt = crypto.rand(300)
    blob = crypto.aead_encrypt(key, pt, aad=b"ctx")
    assert crypto.aead_decrypt(key, blob, aad=b"ctx") == pt
    with pytest.raises(Exception):
        crypto.aead_decrypt(key, blob, aad=b"other")
    bad = bytearray(blob)
    bad[len(bad) // 2] ^= 1
    with pytest.raises(Exception):
        crypto.aead_decrypt(key, bytes(bad), aad=b"ctx")


def test_hkdf_domain_separation():
    key = crypto.rand(32)
    k1 = crypto.hkdf(key, crypto.CTX_DOMAIN_TPL, b"shopA")
    k2 = crypto.hkdf(key, crypto.CTX_DOMAIN_TPL, b"shopB")
    assert k1 != k2
    assert crypto.hkdf(key, crypto.CTX_DOMAIN_TPL, b"shopA") == k1


def test_masked_uid_domain_scoped():
    a = Authority.generate()
    p = a.domain_keys("shopA")
    q = a.domain_keys("shopB")
    mask_a = p.mask("A90000000001")
    mask_b = q.mask("A90000000001")
    # same person, different shops -> unrelated masks
    assert mask_a != mask_b
    # same shop, same person -> stable pseudonym (matching anchor)
    assert p.mask("A90000000001") == mask_a
    assert len(crypto.b64d(mask_a)) == crypto.MASKED_UID_LEN


def test_domain_template_keys_distinct():
    a = Authority.generate()
    ta = a.domain_keys("shopA").domain_tpl_key
    tb = a.domain_keys("shopB").domain_tpl_key
    assert ta != tb


def test_beneficiary_record_sign_verify_and_masking():
    a = Authority.generate()
    rec = a.sign_beneficiary_record({
        "masked_uid": "x", "template_enc": "y", "entitlements": "wheat",
        "valid_from": 1, "valid_to": 2, "cycle_epoch": 1,
    })
    from pdssec.identity import verify_authority_record
    assert verify_authority_record(a.signing_pk_der, rec)
    # tampering with the *signed body* must fail verification
    rec2 = dict(rec)
    body = bytearray(crypto.b64d(rec["body"]))
    body[-2] ^= 0x01
    rec2["body"] = crypto.b64e(bytes(body))
    assert not verify_authority_record(a.signing_pk_der, rec2)
    # tampering with the *signature* must fail verification
    rec3 = dict(rec)
    sig = bytearray(crypto.b64d(rec["sig"]))
    sig[0] ^= 0x01
    rec3["sig"] = crypto.b64e(bytes(sig))
    assert not verify_authority_record(a.signing_pk_der, rec3)
    # an envelope-only change (valid body untouched) is not authenticable
    # evidence by itself - the body is the single source of truth
    rec4 = dict(rec)
    rec4["masked_uid"] = "attacker-edit"
    assert verify_authority_record(a.signing_pk_der, rec4)  # body unchanged


def test_token_mint_verify_and_masked_only():
    a = Authority.generate()
    t = crypto.mint_token(a.signing_sk, "masked-abc", 1, "wheat", 1, 10)
    assert crypto.verify_token(a.signing_sk.public_key(), t)
    # token exposes no UID, only a random id + pseudonym
    body = crypto.token_payload_bytes(t)
    assert b"A9" not in body
    assert b"masked-abc" in body


def test_token_epoch_binding_changes_token():
    a = Authority.generate()
    t1 = crypto.mint_token(a.signing_sk, "m", 1, "wheat", 1, 10)
    t2 = crypto.mint_token(a.signing_sk, "m", 2, "wheat", 1, 10)
    assert t1["token_id"] != t2["token_id"]
    assert crypto.verify_token(a.signing_sk.public_key(), t2)


def test_canonical_roundtrip():
    obj = {"z": 1, "a": "hello", "nested": {"k": "v"}, "b": True}
    body = crypto.canonical(obj)
    parsed = crypto._parse_canonical(body)
    assert parsed["a"] == "hello"
    assert parsed["z"] == "1"
    with pytest.raises(ValueError):
        crypto._parse_canonical(b"a=1&a=2")
    with pytest.raises(ValueError):
        crypto._parse_canonical(b"noequals")


def test_mock_tpm_seal_unseal_policy():
    nv = os.path.join(temp_path(), "tpm.nv")
    t = tpmm.MockTPM(nv)
    t.extend_pcr("boot", b"event1")
    t.seal("app", b"storage-key-material", ["boot"])
    assert t.unseal("app", ["boot"]) == b"storage-key-material"
    # different PCR state must deny unseal (measured boot enforcement)
    t2 = tpmm.MockTPM(nv).load()
    t2.extend_pcr("boot", b"attacker-event")
    with pytest.raises(tpmm.TpmError):
        t2.unseal("app", ["boot"])
    # persistence: reload keeps sealed object
    t3 = tpmm.MockTPM(nv).load()
    assert t3.unseal("app", ["boot"]) == b"storage-key-material"


def test_mock_tpm_anti_rollback_counter():
    nv = os.path.join(temp_path(), "tpm2.nv")
    t = tpmm.MockTPM(nv).load()
    assert t.counter_increment("boot_count") == 1
    t2 = tpmm.MockTPM(nv).load()
    assert t2.counter_read("boot_count") == 1
    with pytest.raises(tpmm.TpmError):
        t2.assert_monotonic("boot_count", last_seen=5)


def test_mock_tpm_detects_nv_tamper():
    nv = os.path.join(temp_path(), "tpm3.nv")
    t = tpmm.MockTPM(nv).load()
    t.seal("k", b"secret", ["boot"])
    with open(nv, "rb") as f:
        data = bytearray(f.read())
    data[len(data) // 2] ^= 0x55
    with open(nv, "wb") as f:
        f.write(bytes(data))
    with pytest.raises(tpmm.TpmError):
        tpmm.MockTPM(nv).load()


def test_fake_tpm_is_detected_by_quote():
    nv = os.path.join(temp_path(), "tpm4.nv")
    real = tpmm.MockTPM(nv).load()
    fake = tpmm.FakeTPM()
    nonce = crypto.rand(16)
    real_quote = real.quote(crypto.gen_ed25519().private_bytes_raw(), nonce)
    with pytest.raises(tpmm.TpmError):
        # fake can't validate its own quote - attestation must fail closed
        fake.verify_quote(crypto.gen_ed25519().private_bytes_raw(),
                          fake.quote(crypto.gen_ed25519().private_bytes_raw(),
                                     nonce))
    assert real_quote["body"]


def test_domain_keys_encrypt_template():
    a = Authority.generate()
    dk = a.domain_keys("shopX")
    tpl = crypto.rand(2048)
    ct = dk.encrypt_template(tpl)
    assert dk.decrypt_template(ct) == tpl
    # cross-shop decryption fails (domain separation)
    other = a.domain_keys("shopY")
    with pytest.raises(Exception):
        other.decrypt_template(ct)


def temp_path() -> str:
    import tempfile
    return tempfile.mkdtemp(prefix="pds-tpm-")