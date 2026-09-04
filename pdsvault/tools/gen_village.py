#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate a simulated village deployment on disk (serialisable snapshot of
the demo used across the test suite).

    python tools/gen_village.py --shops 3 --ben 250 --dir ./demo-village
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pdssec.simulator import build_village  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shops", type=int, default=2)
    p.add_argument("--ben", type=int, default=50)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--dir", required=True)
    args = p.parse_args()
    if os.path.isdir(args.dir):
        shutil.rmtree(args.dir)
    os.makedirs(args.dir, exist_ok=True)
    v = build_village(n_shops=args.shops, n_beneficiaries=args.ben,
                      seed=args.seed, root=args.dir)
    v.sync_all()
    print(f"village ready: domain={v.domain} shops={len(v.shops)} "
          f"beneficiaries={len(v.beneficiaries)} root={args.dir}")


if __name__ == "__main__":
    main()