#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Tamper-injection tool: corrupts a running village deployment exactly like
the adversarial test suite, so researchers can observe detection live.

    python tools/inject.py --dir ./demo-village badsig --shop 0 --uid 0
    python tools/inject.py --dir ./demo-village gap --shop 0 --idx 1
    python tools/inject.py --dir ./demo-village corrupt --shop 0 --bytes 32
    python tools/inject.py --dir ./demo-village rewclock --shop 0 --seconds 3600
    python tools/inject.py --dir ./demo-village faketpm --shop 0
    python tools/inject.py --dir ./demo-village dump --shop 0 --out stolen.sqlite
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pdssec import sync as syncmod  # noqa: E402
from pdssec.simulator import build_village  # noqa: E402


def load_village(args) -> "Village":
    v = build_village(seed=args.seed, root=args.dir)
    # NOTE: we do NOT sync_all() here.  The village was synced by
    # gen_village.py; a second sync against a fresh in-memory server would
    # trip the device's own monotonic replay guard (seq not advancing), which
    # is exactly the property an attacker must never bypass.
    return v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument(
        "kind", choices=["badsig", "gap", "corrupt", "rewclock", "faketpm",
                         "dump"])
    p.add_argument("--shop", type=int, default=0)
    p.add_argument("--uid", type=int, default=0)
    p.add_argument("--idx", type=int, default=1)
    p.add_argument("--bytes", type=int, default=32, dest="nbytes")
    p.add_argument("--seconds", type=int, default=3600)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    v = load_village(args)
    dk = v.authority.domain_keys(v.domain)
    if args.kind == "badsig":
        person = v.beneficiaries[args.uid]
        dsid = syncmod.domain_dsid(dk.domain_uid_key, v.domain,
                                   dk.mask(person["uid"]))
        v.poke_signature(args.shop, dsid)
        print(f"poisoned signature of beneficiary {dsid}; run "
              "`diagnostics` to observe failure at point of use")
    elif args.kind == "gap":
        v.drop_ledger_block(args.shop, args.idx)
        print("dropped a ledger block; the chain now reports a gap and the "
              "device refuses to continue")
    elif args.kind == "corrupt":
        v.corrupt_cache_bytes(args.shop, args.nbytes)
        print(f"corrupted {args.nbytes} bytes of cache.sqlite")
    elif args.kind == "rewclock":
        v.rewind_clock(args.shop, args.seconds)
        print("rewound the secure clock by %d s; next verification must fail "
              "closed as clock tamper" % args.seconds)
    elif args.kind == "faketpm":
        v.swap_fake_tpm(args.shop)
        print("replaced the TPM with a forgery; attestation quote now fails")
    elif args.kind == "dump":
        v.dump_cache(args.shop, args.out or "stolen.sqlite")
        print("cache dumped to", args.out or "stolen.sqlite")


if __name__ == "__main__":
    main()