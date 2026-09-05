"""Seed a realistic first-run demo into the real data root so the labeling UI
is not empty: two consented signers, synthetic samples (keypoints-only), votes,
QA passes, and a shipped manifest.

Run:   python labeling/scripts/seed_demo.py

Idempotent: refuses to re-seed if samples.jsonl already has rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from labeling.backend.store import LabelStore  # noqa: E402
from labeling.scripts.make_synthetic_keypoints import build as synth_build  # noqa: E402

SKIP = {"S-001": "CF-DEMO-001", "S-002": "CF-DEMO-002"}


def main():
    store = LabelStore(ROOT / "data")
    if store.all_samples():
        print("data/annotations/samples.jsonl not empty — refusing to re-seed.")
        return

    import json
    demo_kp = ROOT / "data" / "keypoints" / "demo.json"
    if not demo_kp.exists():
        demo_kp.write_text(json.dumps(synth_build()), encoding="utf-8")

    store.register_consent({
        "signer_id": "S-001", "form_id": SKIP["S-001"], "region": "delhi",
        "age_group": "18-30", "gender": "f", "handedness": "right",
        "native_sign_language": True, "usage": ["training", "ui-demo"],
    })
    store.register_consent({
        "signer_id": "S-002", "form_id": SKIP["S-002"], "region": "chennai",
        "age_group": "30-50", "gender": "m", "handedness": "right",
        "native_sign_language": True, "usage": ["training"],
    })

    demo = [
        ("pds",   "S-001", "delhi",   "ration-card", "I need my ration card."),
        ("pds",   "S-001", "delhi",   "token",       "Where is the token counter?"),
        ("health", "S-002", "chennai", "fever",      "I have fever and a headache."),
        ("legal", "S-002", "chennai", "bail",        "The lawyer will arrange bail."),
    ]
    for i, (domain, signer, region, gloss, english) in enumerate(demo):
        sample = store.register_sample({
            "domain": domain,
            "signer": {"anon_id": signer, "region": region},
            "gloss_seq": gloss.split("-"),
            "source": {"kind": "self-recorded",
                       "provenance_notes": "synthetic demo clip (no real video)"},
            "video": None,
            "keypoints": {"path": "keypoints/demo.json", "frame_count": 150},
            "_consent_status": "granted",
            "_consent_form_id": SKIP[signer],
        })
        sid = sample["sample_id"]
        for ann in ("A1", "A2"):
            store.add_label(sid, {"annotator": ann, "gloss": gloss,
                                  "english_sentence": english, "region": region,
                                  "confidence": 0.9})
        store.set_qa(sid, {"status": "passed", "reviewer": "R1",
                           "notes": "synthetic; keypoint validity checked in increment (b)"})
        print(f"  {sid}: {domain} signer={signer} status={store.get_sample(sid)['status']}")

    from labeling.backend.manifest import write_manifest
    out = write_manifest(store, ROOT / "data", version="v0.1.0-demo")
    print(f"\nmanifest: {out.relative_to(ROOT)}")
    print("Start the server:  python labeling/backend/server.py --port 8123")


if __name__ == "__main__":
    main()