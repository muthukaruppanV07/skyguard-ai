"""Bulk-import approved video clips (and matching keypoints) into the corpus.

Consumes `data/sourced/upload-manifest.csv`. Every column is governance-relevant:

    domain, signer_id, region, video_path, keypoints_path, gloss,
    consent_form_id, consent_status, source_kind, source_url, notes

Rules (matches docs/CONSENT.md + docs/SOURCING.md):
- the signer must already have a consent record (register it in the UI or
  via `store.register_consent` â€” the demo seed creates S-001/S-002)
- consent_status must be `granted` with a form_id that matches the consent log
- domain / region are validated against glossary meta
- idempotent: a row whose video_path is already registered is skipped
- video files must exist under `data/` (they are NOT fetched from URLs)

Run:  python labeling/scripts/import_videos.py [--csv data/sourced/upload-manifest.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from labeling.backend.store import LabelStore  # noqa: E402
from labeling.backend.consensus import normalize_gloss  # noqa: E402

CSV_FIELDNAMES = [
    "domain", "signer_id", "region", "video_path", "keypoints_path", "gloss",
    "consent_form_id", "consent_status", "source_kind", "source_url", "notes",
]


def load_meta(data_root: Path = ROOT):
    meta = json.loads((data_root / "glossaries" / "meta.json").read_text(encoding="utf-8"))
    valid_regions = {r["code"] for r in meta["regions"]}
    valid_domains = set(meta["domains"])
    return valid_domains, valid_regions


def validate_row(row, store, valid_domains, valid_regions, data_root: Path = ROOT) -> list[str]:
    errs = []
    if not row.get("domain") or row["domain"] not in valid_domains:
        errs.append("domain invalid")
    if row.get("region") not in valid_regions:
        errs.append(f"region invalid ({row.get('region')!r})")
    gloss = normalize_gloss(row.get("gloss", ""))
    if not gloss:
        errs.append("gloss empty")
    consent = store.get_consent(row.get("signer_id", ""))
    if consent is None:
        errs.append(f"no consent record for signer {row.get('signer_id')!r}")
    elif row.get("consent_status") != "granted":
        errs.append("consent_status must be granted")
    elif row.get("consent_form_id") and row["consent_form_id"] != consent["form_id"]:
        errs.append("consent_form_id does not match consent log")
    vid = row.get("video_path", "")
    if not vid:
        errs.append("video_path empty")
    else:
        p = data_root / vid
        if not p.exists():
            errs.append(f"video file missing: {vid}")
        elif store_has_video(store, vid):
            errs.append(f"already registered: {vid}")  # treated as skip below
    return errs


def store_has_video(store, video_path):
    for s in store.all_samples():
        if (s.get("video") or {}).get("path") == video_path:
            return True
    return False


def import_rows(store, csv_path, data_root: Path = ROOT) -> tuple[list, list, list]:
    valid_domains, valid_regions = load_meta(data_root)
    created, skipped, failed = [], [], []
    with open(csv_path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for n, row in enumerate(rows, start=2):
        key = row.get("video_path", "")
        if not any(row.values()):
            continue
        errs = validate_row(row, store, valid_domains, valid_regions, data_root)
        if "already registered" in "\n".join(errs):
            skipped.append((key, "already registered"))
            print(f"  row {n}: SKIP {key} (already registered)")
            continue
        if errs:
            failed.append((key, "; ".join(errs)))
            print("  row %d: FAIL %s — %s" % (n, key, "; ".join(errs)))
            continue
        sample = store.register_sample({
            "domain": row["domain"],
            "signer": {"anon_id": row["signer_id"], "region": row["region"]},
            "gloss_seq": normalize_gloss(row["gloss"]).split("-"),
            "video": {"path": row["video_path"], "source_kind": row.get("source_kind", "other")},
            "keypoints": {"path": row["keypoints_path"]} if row.get("keypoints_path") else None,
            "source": {"kind": row.get("source_kind", "other"), "url": row.get("source_url", ""),
                       "provenance_notes": row.get("notes", "")},
            "_consent_status": row["consent_status"],
            "_consent_form_id": row.get("consent_form_id", ""),
        })
        created.append(sample["sample_id"])
        print(f"  row {n}: OK {sample['sample_id']} <- {key} ({row['gloss']})")
    return created, failed, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bulk-import approved video clips")
    parser.add_argument("--csv", default=str(ROOT / "data" / "sourced" / "upload-manifest.csv"))
    parser.add_argument("--template", action="store_true",
                        help="print a blank CSV template and exit")
    args = parser.parse_args(argv)

    if args.template:
        writer = csv.writer(sys.stdout)
        writer.writerow(CSV_FIELDNAMES)
        return

    store = LabelStore(ROOT / "data")
    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"manifest not found: {csv_path}\n"
                 "Generate one with --template or with gen_synthetic_videos.py")
    print(f"importing {csv_path}")
    created, failed, skipped = import_rows(store, csv_path, ROOT / "data")
    print(f"\ncreated {len(created)} samples; {len(failed)} failed; {len(skipped)} skipped")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()