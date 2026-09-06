"""Shared fixtures and helpers for the PDSVault test suite."""

from __future__ import annotations

import tempfile

import pytest

from pdssec import sync as syncmod
from pdssec.device import Device, DeviceConfig
from pdssec.simulator import Village

BOOT_HASH = "100ec4f8a1ef0f9a8478b4c6f5d3e2b1abcdef00"


def dsid_of(v: Village, uid_index: int) -> str:
    dk = v.authority.domain_keys(v.domain)
    person = v.beneficiaries[uid_index]
    masked = dk.mask(person["uid"])
    return syncmod.domain_dsid(dk.domain_uid_key, v.domain, masked)


@pytest.fixture
def village():
    v = Village(n_shops=2, n_beneficiaries=12, now=1_700_000_000,
                seed=1234, boot_hash=BOOT_HASH)
    v.sync_all()
    return v


@pytest.fixture
def shop(village):
    return village.shops[0]


@pytest.fixture
def shop2(village):
    return village.shops[1]


@pytest.fixture
def fresh_workdir():
    d = tempfile.mkdtemp(prefix="pds-test-")
    return d


def make_device(workdir: str, domain: str, authority, fake_tpm: bool = False
                ) -> Device:
    cfg = DeviceConfig(
        workdir=workdir,
        shop_domain=domain,
        domain_uid_key=authority.domain_keys(domain).domain_uid_key,
        authority_pk_der=authority.signing_pk_der,
        provision_boot_hash=BOOT_HASH,
        fake_tpm=fake_tpm,
    )
    return Device(cfg, seed=9)


def mint_and_load_tokens(v: Village) -> list[dict]:
    toks = v.server.mint_tokens_for(
        v.domain, v.beneficiaries, v.cycle_epoch, v.basket,
        v.now - 3600, v.now + 3600 * 24 * 30)
    for shop in v.shops:
        for t in toks:
            try:
                shop.store.insert_token(v.authority.signing_pk_der, t)
            except Exception:
                pass
    return toks