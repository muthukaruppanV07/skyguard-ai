# SPDX-License-Identifier: MIT
"""Simulator: a simulated village, shop terminals, a network toggle, and the
adversary injectors used by the fault-injection suite.

Everything here is a *tool* for demonstrating and testing the security
properties; it never appears on a production device.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import tempfile

from . import crypto
from . import sync as syncmod
from .device import Device, DeviceConfig
from .identity import Authority
from .auth import build_beneficiary_record, build_clock_anchor

DEFAULT_BOOT_HASH = "abc123def456golden-boot-image"

VILLAGE_NAMES = ["Rampur", "Khardi", "Belsar", "Maktapur", "Sundarpur"]


class Village:
    """Simulation of a village PDS deployment.

    One authority (the state PDS agency), one central SyncServer per network
    attachment, `n_shops` shop terminals (each `Device` in its own workdir)
    and `n_beneficiaries` simulated people.

    State is persisted to `<root>/state.json`: the same seed reproduces the
    same authority keys and the same devices, so an injected/corrupted shop
    directory can be reloaded by a later CLI invocation.
    """

    STATE_FILE = "state.json"

    def __init__(self, n_shops: int = 2, n_beneficiaries: int = 40,
                 basket: str = "wheat:5kg;rice:2kg;sugar:1kg",
                 cycle_epoch: int = 1,
                 now: int = 1_700_000_000,
                 seed: int | None = None,
                 root: str | None = None,
                 fake_tpm: bool = False,
                 boot_hash: str = DEFAULT_BOOT_HASH):
        self.rng = random.Random(seed)
        self.root = root or tempfile.mkdtemp(prefix="pdsvillage-")
        os.makedirs(self.root, exist_ok=True)
        self.now = now
        self.basket = basket
        self.cycle_epoch = cycle_epoch
        self.boot_hash = boot_hash
        self.fake_tpm = fake_tpm
        self.seed = seed

        # authority: seeded deterministically so a reloaded village reproduces
        # the same signing keys (master keys NEVER leave this object)
        self.authority = Authority.generate(
            (str(seed).encode() if seed is not None else os.urandom(8)))
        self.domain = VILLAGE_NAMES[self.rng.randrange(len(VILLAGE_NAMES))] + \
            "-shop1"

        # simulated people: full UIDs live in the authority's world only
        self.beneficiaries = []
        for i in range(n_beneficiaries):
            self.beneficiaries.append({
                "uid": "A9" + str(1000000000 + i * 7919),
                "template": self._fake_template(),
                "basket": basket,
            })
        # one person is revoked mid-cycle for the demo tests
        self.revoked_uid = self.beneficiaries[min(3, len(self.beneficiaries) - 1)]["uid"]

        # central server
        self.server = syncmod.SyncServer(self.authority, self.now)
        self._publish_all()

        # shop terminals
        self.shops: list[Device] = []
        for _ in range(n_shops):
            d = self._make_shop()
            self.shops.append(d)

        self._clock_anchor_all()
        self._save_state()

    def _save_state(self) -> None:
        state = {
            "n_shops": len(self.shops), "n_beneficiaries": len(self.beneficiaries),
            "basket": self.basket, "cycle_epoch": self.cycle_epoch,
            "now": self.now, "seed": self.seed, "fake_tpm": self.fake_tpm,
            "boot_hash": self.boot_hash, "domain": self.domain,
        }
        with open(os.path.join(self.root, self.STATE_FILE), "w") as f:
            json.dump(state, f)

    @classmethod
    def load(cls, root: str) -> "Village":
        with open(os.path.join(root, cls.STATE_FILE)) as f:
            st = json.load(f)
        return cls(
            n_shops=st["n_shops"], n_beneficiaries=st["n_beneficiaries"],
            basket=st["basket"], cycle_epoch=st["cycle_epoch"], now=st["now"],
            seed=st["seed"], root=root, fake_tpm=st["fake_tpm"],
            boot_hash=st["boot_hash"])

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    def _fake_template(self) -> list[float]:
        return [self.rng.gauss(0.5, 0.15) for _ in range(64)]

    def _publish_all(self) -> None:
        records = []
        for b in self.beneficiaries:
            rec = build_beneficiary_record(
                self.authority, self.domain, b["uid"], bytes(4),
                b["basket"], self.now - 3600, self.now + 3600 * 24 * 30,
                self.cycle_epoch)
            records.append(rec)
        # records are already authority-signed with this shop's domain key;
        # the device derives the dsid deterministically on apply.
        self.server.publish_domain(self.domain, records)

    def _make_shop(self) -> Device:
        shop_dir = os.path.join(self.root, "shops",
                                f"shop-{len(self.shops)}")
        dk = self.authority.domain_keys(self.domain)
        cfg = DeviceConfig(
            workdir=shop_dir,
            shop_domain=self.domain,
            domain_uid_key=dk.domain_uid_key,
            authority_pk_der=self.authority.signing_pk_der,
            provision_boot_hash=self.boot_hash,
            fake_tpm=self.fake_tpm,
        )
        dev = Device(cfg, seed=self.rng.randrange(1 << 30))
        # enroll matcher to mirror the encrypted store
        for i, b in enumerate(self.beneficiaries):
            masked = dk.mask(b["uid"])
            dsid = syncmod.domain_dsid(dk.domain_uid_key, self.domain, masked)
            dev.matcher.enroll(dsid, b["template"])
        return dev

    def _clock_anchor_all(self) -> None:
        for shop in self.shops:
            anchor = build_clock_anchor(self.authority, self.now, self.domain)
            shop.clock.set_anchor(anchor, self.authority.signing_pk_der)

    # ------------------------------------------------------------------ #
    # sync wiring (the "network" through which shops attach)
    # ------------------------------------------------------------------ #

    def shop_server(self, shop: Device) -> syncmod.SyncServer:
        return self.server

    def sync_all(self) -> list[dict]:
        out = []
        for shop in self.shops:
            out.append(shop.sync(self.server))
        return out

    # ------------------------------------------------------------------ #
    # adversary injectors
    # ------------------------------------------------------------------ #

    def dump_cache(self, shop_index: int, dst_path: str) -> None:
        """Adversary steals a shop cache (simulation of physical seizure +
        cache dump on an attacker laptop)."""
        src = os.path.join(self.root, "shops", f"shop-{shop_index}",
                           "cache.sqlite")
        shutil.copyfile(src, dst_path)

    def corrupt_cache_bytes(self, shop_index: int, n_bytes: int = 64,
                            offset: int = 0) -> None:
        path = os.path.join(self.root, "shops", f"shop-{shop_index}",
                            "cache.sqlite")
        with open(path, "r+b") as f:
            f.seek(offset)
            patch = self.rng.randbytes(min(n_bytes, os.path.getsize(path)
                                           - offset))
            f.write(patch)

    def drop_ledger_block(self, shop_index: int, idx: int) -> None:
        """Delete a ledger block to simulate a chain gap (hostile cleanup)."""
        shop = self.shops[shop_index]
        con = shop.store._connect()
        try:
            con.execute("DELETE FROM ledger_block WHERE idx=?", (idx,))
            con.commit()
        finally:
            con.close()

    def drop_ledger_txn(self, shop_index: int, txn_hash: str) -> None:
        shop = self.shops[shop_index]
        con = shop.store._connect()
        try:
            con.execute("DELETE FROM ledger_txn WHERE txn_hash=?",
                        (txn_hash,))
            con.commit()
        finally:
            con.close()

    def poke_signature(self, shop_index: int, dsid: str) -> None:
        """Flip one byte inside a signed beneficiary body -> signature
        must then fail verification (poisoned cache)."""
        shop = self.shops[shop_index]
        con = shop.store._connect()
        try:
            row = con.execute("SELECT body FROM beneficiaries WHERE dsid=?",
                              (dsid,)).fetchone()
            if row:
                body = bytearray(crypto.b64d(row[0]))
                body[0] ^= 0x01
                con.execute("UPDATE beneficiaries SET body=? WHERE dsid=?",
                            (crypto.b64e(bytes(body)), dsid))
                con.commit()
        finally:
            con.close()

    def rewind_clock(self, shop_index: int, seconds: int) -> None:
        """Attempt to rewind the secure clock (must be detected as tamper)."""
        shop = self.shops[shop_index]
        prev = shop.clock._last_anchor_unix
        shop.clock._last_anchor_unix = prev - seconds

    def swap_fake_tpm(self, shop_index: int) -> None:
        """Simulates an attacker replacing the secure element with a forgery.
        In production this is caught at attestation/quote time; the simulator
        replaces the object in memory."""
        from . import tpm as tpmm
        self.shops[shop_index].tpm = tpmm.FakeTPM()

    def query_window(self, tok: dict) -> dict:
        """Central redemption oracle: do we have witnesses this token is
        already redeemed?  (Used by tests to assert cross-shop dedup.)"""
        return {"known_redeemed": tok.get("token_id") in
                self.server.redeemed_token_ids}


def build_village(**kw) -> Village:
    return Village(**kw)