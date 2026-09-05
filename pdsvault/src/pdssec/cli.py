# SPDX-License-Identifier: MIT
"""Operator CLI / simulation driver for PDSVault.

Demonstrates the full offline flow and exposes the tamper-injection model:
    python -m pdssec.cli sim --shops 2 --ben 40
    python -m pdssec.cli verify --shop 0 --index 0 --genuine --network-off
    python -m pdssec.cli pad-report
    python -m pdssec.cli diagnostics --shop 0
    python -m pdssec.cli sync --shop 0
    python -m pdssec.cli inject --shop 0 badsig --dsid ...
    python -m pdssec.cli inject --shop 0 gap --idx 1
    python -m pdssec.cli inject --shop 0 corrupt --bytes 32
    python -m pdssec.cli inject --shop 0 rewclock --seconds 3600
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import crypto
from . import sync as syncmod
from .entitlement import EntitlementDenied
from .pad import PADTestRig, DeterministicPAD
from .simulator import Village, build_village


def _village(args) -> Village:
    if args.dir and os.path.exists(os.path.join(args.dir, Village.STATE_FILE)):
        return Village.load(args.dir)
    return build_village(
        n_shops=args.shops, n_beneficiaries=args.ben, seed=args.seed,
        fake_tpm=args.fake_tpm, root=args.dir,
    )


def _shop(v: Village, index: int):
    return v.shops[index % len(v.shops)]


def cmd_sim(args) -> int:
    v = _village(args)
    print(f"[village] domain={v.domain} shops={len(v.shops)} "
          f"beneficiaries={len(v.beneficiaries)} root={v.root}")
    print("[sync] shops attach to authority (this would be USB/2G)...")
    for r in v.sync_all():
        print("  sync result:", r)
    dk = v.authority.domain_keys(v.domain)
    shop = v.shops[0]
    person = v.beneficiaries[0]
    dsid = syncmod.domain_dsid(dk.domain_uid_key, v.domain,
                               dk.mask(person["uid"]))
    print(f"\n[offline verify] beneficiary dsid={dsid}")
    try:
        res = shop.verify_face(operator="op-1", target_dsid=dsid,
                               genuine=True, wall_now=v.now)
        print("   -> eligible:", res["verdict"], round(res["score"], 3))
    except EntitlementDenied as e:
        print("   -> denied:", e.code, e.reason)
    print("\n[offline redeem]")
    toks = v.server.mint_tokens_for(v.domain, v.beneficiaries,
                                    v.cycle_epoch, v.basket,
                                    v.now - 3600, v.now + 3600 * 24 * 30)
    v.server.tokens = toks
    for shop in v.shops:
        for t in toks[:10]:
            try:
                shop.store.insert_token(v.authority.signing_pk_der, t)
            except Exception:
                pass
    t = toks[0]
    try:
        r = shop.redeem(t["token_id"], "op-1")
        print("   ->", r["verdict"], r["basket"])
        try:
            shop.redeem(t["token_id"], "op-1")
            print("      (unexpected: second redeem allowed)")
        except EntitlementDenied as e:
            print("      denied:", e.code)
    except EntitlementDenied as e:
        print("   -> redeem failed:", e.code, e.reason)
    print("\n[ledger tail]")
    for row in shop.ledger.tail(6):
        print("   ", row["kind"], row["ts"], list(row["data"].keys())[:2])
    print("\ndone. cache sqlite at:", os.path.join(shop.cfg.workdir,
                                                   "cache.sqlite"))
    return 0


def cmd_verify(args) -> int:
    v = _village(args)
    v.sync_all()
    shop = _shop(v, args.shop)
    dk = v.authority.domain_keys(v.domain)
    person = v.beneficiaries[args.index % len(v.beneficiaries)]
    dsid = syncmod.domain_dsid(dk.domain_uid_key, v.domain,
                               dk.mask(person["uid"]))
    try:
        res = shop.verify_face(operator=args.operator, target_dsid=dsid,
                               genuine=not args.impostor,
                               liveness_kind=args.liveness,
                               wall_now=v.now)
        print(json.dumps(res, indent=2))
        return 0
    except EntitlementDenied as e:
        print(json.dumps({"denied": e.code, "reason": e.reason}, indent=2))
        return 2
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}, indent=2))
        return 3


def cmd_sync(args) -> int:
    v = _village(args)
    shop = _shop(v, args.shop)
    print(json.dumps(shop.sync(v.shop_server(shop)), indent=2))
    return 0


def cmd_pad_report(args) -> int:
    rig = PADTestRig(DeterministicPAD())
    rig.generate_set(n_bonafide=200, n_per_attack=100)
    t = 0.5
    print(rig.report(t))
    for t in (0.4, 0.5, 0.6):
        r = rig.evaluate(t)
        print(f"threshold={t}: overall APCER={r['overall_APCER']:.3f} "
              f"BPCER={r['BPCER']:.3f}")
    return 0


def cmd_diagnostics(args) -> int:
    v = _village(args)
    shop = _shop(v, args.shop)
    diag = shop.self_diagnostics()
    print(json.dumps(diag, indent=2))
    print("quarantine:", shop.store.quarantine_count())
    return 0


def cmd_inject(args) -> int:
    v = _village(args)
    shop = _shop(v, args.shop)
    if args.kind == "badsig":
        dk = v.authority.domain_keys(v.domain)
        person = v.beneficiaries[0]
        dsid = syncmod.domain_dsid(dk.domain_uid_key, v.domain,
                                   dk.mask(person["uid"]))
        v.poke_signature(args.shop, dsid)
        print("poisoned one beneficiary signature; run `diagnostics --shop` "
              "to see it fail verification")
    elif args.kind == "gap":
        v.drop_ledger_block(args.shop, args.idx)
        print(f"dropped ledger block {args.idx}; `diagnostics` should report "
              "a chain gap")
    elif args.kind == "corrupt":
        v.corrupt_cache_bytes(args.shop, args.bytes)
        print("corrupted cache bytes")
    elif args.kind == "rewclock":
        v.rewind_clock(args.shop, args.seconds)
        print(f"rewound clock by {args.seconds}s; next verify must fail "
              "closed as clock tamper")
    elif args.kind == "faketpm":
        v.swap_fake_tpm(args.shop)
        print("swapped in a fake TPM; attestation quote must fail")
    else:
        print("unknown injection kind")
        return 2
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pdsvault")
    p.add_argument("--dir", default=None)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--shops", type=int, default=2)
    p.add_argument("--ben", type=int, default=40)
    p.add_argument("--fake-tpm", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sim")
    _defaults(sp)

    sp = sub.add_parser("verify")
    _defaults(sp)
    sp.add_argument("--shop", type=int, default=0)
    sp.add_argument("--index", type=int, default=0)
    sp.add_argument("--operator", default="op-1")
    sp.add_argument("--impostor", action="store_true")
    sp.add_argument("--liveness", default="bonafide")

    sp = sub.add_parser("sync")
    _defaults(sp)
    sp.add_argument("--shop", type=int, default=0)

    sp = sub.add_parser("pad-report")
    _defaults(sp, allow=())

    sp = sub.add_parser("diagnostics")
    _defaults(sp)
    sp.add_argument("--shop", type=int, default=0)

    sp = sub.add_parser("inject")
    _defaults(sp)
    sp.add_argument("--shop", type=int, default=0)
    sp.add_argument("kind", choices=["badsig", "gap", "corrupt", "rewclock",
                                     "faketpm"])
    sp.add_argument("--dsid", default=None)
    sp.add_argument("--idx", type=int, default=1)
    sp.add_argument("--bytes", type=int, default=32, dest="nbytes")
    sp.add_argument("--seconds", type=int, default=3600)

    args = p.parse_args(argv)
    return globals()["cmd_" + args.cmd.replace("-", "_")](args)


def _defaults(sp, allow=("shops", "ben", "seed", "dir", "fake_tpm")):
    if "shops" in allow:
        sp.add_argument("--shops", type=int, default=2)
    if "ben" in allow:
        sp.add_argument("--ben", type=int, default=40)
    if "seed" in allow:
        sp.add_argument("--seed", type=int, default=7)
    if "dir" in allow:
        sp.add_argument("--dir", default=None)
    if "fake_tpm" in allow:
        sp.add_argument("--fake-tpm", action="store_true")


if __name__ == "__main__":
    sys.exit(main())