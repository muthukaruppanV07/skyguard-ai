"""Versioned dataset manifest export.

A manifest is the ONLY thing BhashaSetu releases about the dataset. It pins:

- schema + dataset version and timestamp
- every eligible sample with: domain, gloss_seq (consensus), english sentence,
  signer (anon), region/dialect, consent form id, QA result, source provenance,
  keypoint stats, label votes + agreement
- sha256 checksums of raw video + keypoints files (files themselves are not in git)

Eligibility (all must hold — see docs/CONSENT.md + data/README.md):
    consent granted, >= MIN_ANNOTATORS votes, consensus agreed, qa passed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .consensus import compute_consensus, normalize_gloss
from .store import LabelStore

DATASET_VERSION = "v0.1.0"
SCHEMA_VERSION = "sample.schema.v1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _eligible(sample: dict, consensus: dict) -> bool:
    consent = sample.get("consent", {})
    if consent.get("status") != "granted" or not consent.get("form_id"):
        return False
    if sample.get("status") == "withdrawn":
        return False
    if sample.get("qa", {}).get("status") != "passed":
        return False
    if consensus.get("status") != "agreed":
        return False
    return True


def build_manifest(store: LabelStore, data_root: Path, version: str = DATASET_VERSION) -> dict:
    samples = []
    for sample in store.all_samples():
        labels = store.latest_labels_for(sample["sample_id"])
        consensus = compute_consensus(labels)
        if not _eligible(sample, consensus):
            continue

        rec = {
            "sample_id": sample["sample_id"],
            "domain": sample["domain"],
            "gloss_seq": normalize_gloss(consensus["gloss"]).split("-"),
            "isl_gloss": consensus["gloss"],
            "english_sentence": consensus["english_sentence"],
            "osv_english": sample.get("english_sentence", ""),
            "signer": {
                "anon_id": sample["signer"].get("anon_id", ""),
                "region": sample["signer"].get("region", ""),
                "age_group": sample["signer"].get("age_group", ""),
                "gender": sample["signer"].get("gender", ""),
                "handedness": sample["signer"].get("handedness", ""),
                "native_sign_language": sample["signer"].get("native_sign_language", ""),
            },
            "dialect": {
                "region": sample.get("dialect", {}).get("region", ""),
                "variant_notes": sample.get("dialect", {}).get("variant_notes", ""),
            },
            "consent": {"form_id": sample["consent"].get("form_id", ""),
                        "usage": sample["consent"].get("usage", [])},
            "qa": sample.get("qa", {}),
            "source": sample.get("source"),
            "video": {
                "path": (sample.get("video") or {}).get("path", ""),
                "duration_s": (sample.get("video") or {}).get("duration_s"),
                "fps": (sample.get("video") or {}).get("fps"),
                "source_kind": (sample.get("video") or {}).get("source_kind", ""),
            },
            "keypoints": sample.get("keypoints"),
            "labels_votes": len(labels),
            "consensus_agreement": consensus["agreement"],
            "consensus_status": consensus["status"],
        }

        for field in ("video", "keypoints"):
            info = sample.get(field) or {}
            rel = info.get("path")
            if rel:
                p = data_root / rel
                if p.exists():
                    rec[field]["checksum_sha256"] = _sha256(p)
        samples.append(rec)

    manifest = {
        "dataset_version": version,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_count": len(samples),
        "by_domain": {
            d: len([s for s in samples if s["domain"] == d])
            for d in ("pds", "health", "legal")
        },
        "note": "Consented + QA-passed + consensus-agreed samples only; "
                "raw media + keypoints distributed separately with checksums.",
        "samples": samples,
    }
    return manifest


def write_manifest(store: LabelStore, data_root: Path, version: str = DATASET_VERSION) -> Path:
    manifest = build_manifest(store, data_root, version)
    out_dir = Path(data_root) / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"bhashasetu-{version}-{stamp}.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out