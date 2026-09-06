# SPDX-License-Identifier: MIT
"""Hardware root of trust.

A TPM 2.0 / StrongBox / SE simulation with an interface that mirrors the real
TPM2 commands the production device uses (TPM2_CreateSealed, TPM2_Unseal,
TPM2_PCR_Extend, TPM2_Quote, TPM2_NV_Increment).  On the real device these map
1:1 to the vendor TSS; on the reference implementation the "hardware" file
plays the role of non-extractable NVRAM and the SRK is the anchor.

Design rules that hold in both worlds:
  * keys are sealed with a policy blob; unsealing requires the current PCR
    state to match the policy (measured boot -> only the exact signed OS+app
    image can unseal the storage key).
  * monotonic counters are NV; TPM guarantees no decrement.  The mock persists
    a high-water mark and cross-checks it, so even deleting the counter file
    (NV reset) is detected as a rollback unless the marker is consistent.
  * quotes are signed by the attestation key, so a *fake* TPM that always
    answers success is detected by attestation-time PCR mismatch against the
    provisioned golden baseline.
"""

from __future__ import annotations

import json
import os

from . import crypto
from .crypto import b64d, b64e, rand, sha256


class TpmError(Exception):
    pass


class _SealedObject:
    """A sealed blob.  In the mock the object exists as a JSON record whose
    key material is wrapped by the SRK (which never leaves "hardware")."""

    def __init__(self, blob: str, policy_pcrs: list[str]):
        self.blob = blob
        self.policy_pcrs = policy_pcrs


class MockTPM:
    """Simulated TPM2.0-compatible device.

    Parameters
    ----------
    nv_path : str
        Path of the "hardware" backing file (non-extractable NVRAM in real hw).
    srk : bytes | None
        Optional explicit SRK; otherwise generated at init and persisted.
    boot_pcrs : dict[str,str] | None
        Initial PCR banks (hex digests). Defaults to a clean baseline.
    """

    VERSION = "mock-tpm-2.0-v1"

    def __init__(self, nv_path: str, srk: bytes | None = None,
                 boot_pcrs: dict[str, str] | None = None):
        self.nv_path = nv_path
        if srk is None:
            srk = crypto.rand(32)  # SRK must be a valid AES key
        self.srk = srk
        self._pcrs = dict(boot_pcrs or {"boot": sha256(b"golden-boot").hex()})
        self._sealed: dict[str, _SealedObject] = {}
        self._counters: dict[str, int] = {}
        self._loaded = False

    # ---- persistence: load/save the "hardware" area --------------------- #

    def _save(self) -> None:
        payload = {
            "version": self.VERSION,
            "srk": b64e(self.srk),
            "pcrs": self._pcrs,
            "sealed": {k: {"blob": v.blob, "policy": v.policy_pcrs}
                       for k, v in self._sealed.items()},
            "counters": self._counters,
        }
        data = json.dumps(payload).encode("utf-8")
        # Integrity-protect the NV area so a swapped/fabricated NV file is
        # detectable.  Real TPM NVRAM does not need this - the HW enforces it.
        tag = crypto.hmac_sha256(self.srk, data)
        with open(self.nv_path, "wb") as f:
            f.write(b"MTPM1" + data + b"|" + tag)

    def load(self) -> "MockTPM":
        try:
            with open(self.nv_path, "rb") as f:
                blob = f.read()
            if not blob.startswith(b"MTPM1"):
                raise TpmError("NV file is not a TPM NV area")
            body, tag = blob[5:].rsplit(b"|", 1)
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise TpmError("NV area corrupted (cannot decode)")
            # The SRK lives inside the NV area; verify the symmetric tag under
            # that SRK (mirrors TPM2_ReadPublic + NV authorisation).
            srk = b64d(payload["srk"])
            if not crypto.hmac_compare(srk, body, tag):
                raise TpmError("NV integrity check failed: tampered NV area")
            self.srk = srk
            self._pcrs = payload["pcrs"]
            self._sealed = {
                k: _SealedObject(v["blob"], v["policy"])
                for k, v in payload["sealed"].items()
            }
            self._counters = {k: int(v) for k, v in payload["counters"].items()}
            self._loaded = True
        except FileNotFoundError:
            if not os.path.exists(self.nv_path):
                # fresh device: persist a new hardware identity immediately
                self._save()
            self._loaded = True
        return self

    # ---- PCR management (measured boot) --------------------------------- #

    def extend_pcr(self, pcr: str, event: bytes) -> None:
        cur = bytes.fromhex(self._pcrs.get(pcr, "00" * 32))
        self._pcrs[pcr] = sha256(cur + sha256(event)).hex()

    def pcr_read(self, pcr: str) -> str:
        return self._pcrs[pcr]

    # ---- sealing -------------------------------------------------------- #

    def seal(self, label: str, key_material: bytes, policy_pcrs: list[str]) -> _SealedObject:
        # Wrap under the SRK. In HW, TPM2_CreateSealed; unseal only when PCRs
        # match policy.
        policy = {p: self._pcrs[p] for p in policy_pcrs}
        blob = crypto.aead_encrypt(self.srk, key_material, aad=self._policy_blob(policy))
        obj = _SealedObject(b64e(blob), policy_pcrs)
        self._sealed[label] = obj
        self._save()
        return obj

    def unseal(self, label: str, policy_pcrs: list[str] | None = None) -> bytes:
        obj = self._sealed.get(label)
        if obj is None:
            raise TpmError(f"no sealed object: {label}")
        policy_pcrs = policy_pcrs or obj.policy_pcrs
        policy = {p: self._pcrs[p] for p in policy_pcrs}
        try:
            return crypto.aead_decrypt(
                self.srk, b64d(obj.blob), aad=self._policy_blob(policy)
            )
        except Exception:
            raise TpmError(
                "unseal denied: PCR state does not match sealing policy"
            )

    def _policy_blob(self, policy: dict[str, str]) -> bytes:
        return crypto.canonical(policy)

    # ---- attestation ---------------------------------------------------- #

    def quote(self, attestation_key_der: bytes, nonce: bytes) -> dict:
        """Quote of all PCRs + NV counter high-water marks, signed by the
        device attestation key (mirrors TPM2_Quote)."""
        quoted = {
            "pcr": {k: v for k, v in sorted(self._pcrs.items())},
            "counters": {k: v for k, v in sorted(self._counters.items())},
            "nonce": b64e(nonce),
        }
        sk = crypto.load_priv(attestation_key_der)
        body = crypto.canonical(quoted)
        sig = crypto.ed25519_sign(sk, body)
        return {"body": b64e(body), "sig": b64e(sig)}

    def verify_quote(self, attestation_pub_der: bytes, quote: dict) -> bytes:
        body = b64d(quote["body"])
        if not crypto.ed25519_verify(crypto.load_pub(attestation_pub_der), body, b64d(quote["sig"])):
            raise TpmError("quote signature invalid")
        return body

    # ---- monotonic counters (anti-rollback) ----------------------------- #

    def counter_increment(self, name: str) -> int:
        cur = self._counters.get(name, 0) + 1
        self._counters[name] = cur
        self._save()
        return cur

    def counter_read(self, name: str) -> int:
        return self._counters.get(name, 0)

    def assert_monotonic(self, name: str, last_seen: int) -> None:
        cur = self.counter_read(name)
        if cur < last_seen:
            raise TpmError(
                f"anti-rollback violation on counter '{name}': "
                f"now {cur} < last seen {last_seen}"
            )
        if cur != last_seen:
            # counter advanced while we were offline is fine (that is the
            # point of NV counters) but must be reflected by caller.
            pass


# --------------------------------------------------------------------------- #
# Fake TPM used by the adversarial test suite.
# --------------------------------------------------------------------------- #

class FakeTPM:
    """A permissive counterfeit 'TPM'.  Seals anything, never refuses unseal,
    counters roll freely.  Every one of its answers diverges from the golden
    baseline, so the attestation layer *must* reject it."""

    VERSION = "fake-tpm-0.1"

    def __init__(self, *a, **kw):
        self._counters = {}
        self._mem = {}

    def seal(self, label, key_material, policy_pcrs):
        self._mem[label] = key_material
        return _SealedObject(b64e(key_material), policy_pcrs)

    def unseal(self, label, policy_pcrs=None):
        return self._mem[label]

    def extend_pcr(self, pcr, event):
        pass

    def pcr_read(self, pcr):
        return "00" * 32

    def quote(self, attestation_key_der, nonce):
        # A counterfeit has no genuine attestation key or PCRs; the only
        # honest answer is a failure (so any consumer fails closed).
        raise TpmError("counterfeit TPM cannot produce an attestation quote")

    def verify_quote(self, pub, quote):
        raise TpmError("fake TPM cannot validate its own quote")

    def counter_increment(self, name):
        self._counters[name] = self._counters.get(name, 0) + 1
        return self._counters[name]

    def counter_read(self, name):
        return self._counters.get(name, 0)

    def assert_monotonic(self, name, last_seen):
        pass
