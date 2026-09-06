"""Append-only JSONL store for the BhashaSetu labeling tool.

Zero external dependencies (Python stdlib). All dataset state lives under
``data/annotations/`` as append-only JSONL logs, giving a built-in audit trail:

    samples.jsonl    sample registry (metadata, status lifecycle)
    labels.jsonl     every annotator vote (multi-annotator)
    qa.jsonl         QA pass/reject decisions
    consent.jsonl    consent records per anonymous signer
    audit.log        human-readable trail of every mutation

Concurrency: a per-file lock + ``os.replace`` atomic swap makes writes crash-safe.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

ANNOTATIONS = "annotations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AtomicJSONLStore:
    """Append-only JSONL file with per-file lock and atomic append."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        with open(self.path, "r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def append(self, record: dict) -> dict:
        rec = dict(record)
        with self._lock:
            tmp = self.path.with_suffix(".jsonl.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                if self.path.exists():
                    with open(self.path, "r", encoding="utf-8") as src:
                        fh.write(src.read())
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(tmp, self.path)  # atomic swap
        return rec

    def rows(self) -> list[dict]:
        with self._lock:
            return self._read()

    def replace(self, records: list[dict]):
        """Rewrites the whole file (used for withdrawal rewrites, not hot path)."""
        with self._lock:
            tmp = self.path.with_suffix(".jsonl.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(tmp, self.path)


class LabelStore:
    """Facade over the JSONL logs: samples, labels, qa, consent, audit."""

    def __init__(self, data_root: Path):
        self.root = Path(data_root)
        self.ann = self.root / ANNOTATIONS
        self.ann.mkdir(parents=True, exist_ok=True)
        self.samples = AtomicJSONLStore(self.ann / "samples.jsonl")
        self.labels = AtomicJSONLStore(self.ann / "labels.jsonl")
        self.qa = AtomicJSONLStore(self.ann / "qa.jsonl")
        self.consent = AtomicJSONLStore(self.ann / "consent.jsonl")
        self._audit_file = self.ann / "audit.log"
        self._audit_lock = threading.Lock()

    # ------------------------------------------------------------- audit trail
    def _audit(self, action: str, payload: dict):
        line = f"{_now()} {action} {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        with self._audit_lock:
            with open(self._audit_file, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    # ------------------------------------------------------------- sample ids
    SAMPLE_ID_RE = re.compile(r"^ISL-(PDS|HTH|LEG)-\d{5}$")

    def next_sample_id(self, domain: str) -> str:
        prefix = {"pds": "PDS", "health": "HTH", "legal": "LEG"}[domain]
        highest = 0
        for s in self.samples.rows():
            if s.get("sample_id", "").startswith(f"ISL-{prefix}-"):
                try:
                    highest = max(highest, int(s["sample_id"].rsplit("-", 1)[1]))
                except ValueError:
                    pass
        return f"ISL-{prefix}-{highest + 1:05d}"

    # ------------------------------------------------------------- samples
    def register_sample(self, record: dict, actor: str = "cli") -> dict:
        if record.get("domain") not in ("pds", "health", "legal"):
            raise ValueError(f"bad domain {record.get('domain')!r}")
        sample_id = record.get("sample_id") or self.next_sample_id(record["domain"])
        if not self.SAMPLE_ID_RE.match(sample_id):
            raise ValueError(f"bad sample_id {sample_id!r}")
        sample = {
            "sample_id": sample_id,
            "domain": record["domain"],
            "status": "registered",
            "created_at": _now(),
            "version": record.get("version", "v0.1.0"),
            "gloss_seq": record.get("gloss_seq", []),
            "english_sentence": record.get("english_sentence", ""),
            "dialect": record.get("dialect", {"region": record.get("region", "")}),
            "video": record.get("video"),
            "keypoints": record.get("keypoints"),
            "source": record.get("source"),
            "signer": record.get("signer"),
            "consent": {
                "status": record.get("_consent_status", "pending"),
                "form_id": record.get("_consent_form_id", ""),
                "usage": record.get("_consent_usage", []),
            },
            "labels": [],
            "consensus": None,
            "qa": {"status": "pending", "reviewer": "", "notes": "", "ts": ""},
        }
        self.samples.append(sample)
        self._audit("register_sample", {"actor": actor, "sample_id": sample_id})
        return sample

    def get_sample(self, sample_id: str) -> dict | None:
        for s in self.samples.rows():
            if s["sample_id"] == sample_id:
                return s
        return None

    def all_samples(self) -> list[dict]:
        return self.samples.rows()

    def set_status(self, sample_id: str, status: str, actor: str = "cli"):
        rows = self.samples.rows()
        for s in rows:
            if s["sample_id"] == sample_id:
                s["status"] = status
                break
        else:
            raise KeyError(sample_id)
        self.samples.replace(rows)
        self._audit("set_status", {"actor": actor, "sample_id": sample_id, "status": status})

    # ------------------------------------------------------------- labels
    def add_label(self, sample_id: str, label: dict, actor: str = "cli") -> dict:
        self.get_sample(sample_id)  # raises KeyError if missing
        if not label.get("annotator"):
            raise ValueError("annotator required")
        if not label.get("gloss", "").strip():
            raise ValueError("gloss required")
        row = {
            "sample_id": sample_id,
            "annotator": label["annotator"],
            "gloss": label["gloss"].strip(),
            "english_sentence": label.get("english_sentence", "").strip(),
            "region": label.get("region", ""),
            "dialect_notes": label.get("dialect_notes", ""),
            "confidence": float(label.get("confidence", 0.5)),
            "flags": label.get("flags", []),
            "ts": _now(),
        }
        self.labels.append(row)
        self._audit("add_label", {"actor": actor, "sample_id": sample_id,
                                  "annotator": row["annotator"]})
        return row

    def labels_for(self, sample_id: str) -> list[dict]:
        return [l for l in self.labels.rows() if l["sample_id"] == sample_id]

    def latest_labels_for(self, sample_id: str) -> list[dict]:
        """One vote per annotator — the most recent wins (labels are append-only)."""
        latest: dict[str, dict] = {}
        for l in self.labels_for(sample_id):
            latest[l["annotator"]] = l
        return sorted(latest.values(), key=lambda r: r["ts"])

    # ------------------------------------------------------------- qa
    def set_qa(self, sample_id: str, decision: dict, actor: str = "cli") -> dict:
        status = decision.get("status")
        if status not in ("passed", "rejected"):
            raise ValueError("qa status must be passed|rejected")
        row = {
            "sample_id": sample_id,
            "status": status,
            "reviewer": decision.get("reviewer", actor),
            "notes": decision.get("notes", ""),
            "ts": _now(),
        }
        self.qa.append(row)
        samples = self.samples.rows()
        for s in samples:
            if s["sample_id"] == sample_id:
                s["qa"] = row
                s["status"] = "qa_pass" if status == "passed" else "qa_reject"
                break
        self.samples.replace(samples)
        self._audit("qa", {"actor": actor, "sample_id": sample_id, "status": status})
        return row

    def qa_for(self, sample_id: str) -> dict | None:
        rows = [q for q in self.qa.rows() if q["sample_id"] == sample_id]
        return rows[-1] if rows else None

    # ------------------------------------------------------------- consent
    def register_consent(self, rec: dict, actor: str = "cli") -> dict:
        signer_id = rec.get("signer_id", "")
        if not re.match(r"^S-\d{3,}$", signer_id):
            raise ValueError(f"bad signer_id {signer_id!r}")
        row = {
            "signer_id": signer_id,
            "form_id": rec.get("form_id", ""),
            "status": rec.get("status", "granted"),
            "usage": rec.get("usage", []),
            "region": rec.get("region", ""),
            "age_group": rec.get("age_group", ""),
            "gender": rec.get("gender", ""),
            "handedness": rec.get("handedness", ""),
            "native_sign_language": bool(rec.get("native_sign_language", True)),
            "ts": _now(),
        }
        self.consent.append(row)
        self._audit("register_consent", {"actor": actor, "signer_id": signer_id})
        return row

    def get_consent(self, signer_id: str) -> dict | None:
        rows = [c for c in self.consent.rows() if c["signer_id"] == signer_id]
        return rows[-1] if rows else None

    def withdraw(self, signer_id: str, actor: str = "cli") -> list[str]:
        """Withdraw a signer: mark their samples withdrawn and log the removal."""
        rows = self.consent.rows()
        for c in rows:
            if c["signer_id"] == signer_id:
                c["status"] = "withdrawn"
        self.consent.replace(rows)
        impacted = [s["sample_id"] for s in self.all_samples()
                    if s.get("signer", {}).get("anon_id") == signer_id]
        samples = self.samples.rows()
        for s in samples:
            if s.get("signer", {}).get("anon_id") == signer_id:
                s["status"] = "withdrawn"
        self.samples.replace(samples)
        self._audit("withdraw", {"actor": actor, "signer_id": signer_id,
                                 "samples_removed": len(impacted)})
        return impacted

    # ------------------------------------------------------------- stats
    def stats(self) -> dict:
        samples = self.all_samples()
        by_domain: dict[str, dict] = {}
        signers: dict[str, dict] = {}
        for s in samples:
            d = by_domain.setdefault(s["domain"], {"total": 0, "by_status": {}})
            d["total"] += 1
            d["by_status"][s["status"]] = d["by_status"].get(s["status"], 0) + 1
            signer = s.get("signer", {})
            sid = signer.get("anon_id", "?")
            if sid not in signers:
                signers[sid] = {"anon_id": sid, "samples": 0, **{
                    k: signer.get(k, "") for k in
                    ("region", "age_group", "gender", "handedness", "native_sign_language")}}
            signers[sid]["samples"] += 1
        return {
            "samples_total": len(samples),
            "labels_total": len(self.labels.rows()),
            "by_domain": by_domain,
            "signers": sorted(signers.values(), key=lambda s: s["anon_id"]),
            "signer_diversity": {
                "signers": len(signers),
                "regions": sorted({s["region"] for s in signers.values() if s["region"]}),
                "age_groups": sorted({s["age_group"] for s in signers.values() if s["age_group"]}),
                "genders": sorted({s["gender"] for s in signers.values() if s["gender"]}),
            },
            "generated_at": _now(),
        }