"""Unit tests for versioned manifest export (eligibility + checksums)."""

import json
import tempfile
import unittest
from pathlib import Path

from labeling.backend.manifest import build_manifest, write_manifest
from labeling.backend.store import LabelStore


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = LabelStore(self.root)
        (self.root / "raw").mkdir()
        (self.root / "keypoints").mkdir()
        (self.root / "raw" / "ISL-PDS-00001.mp4").write_bytes(b"FAKEVIDEO")
        (self.root / "keypoints" / "ISL-PDS-00001.json").write_bytes(b'{"frames":[]}')

    def tearDown(self):
        self.tmp.cleanup()

    def _register_full(self):
        s = self.store.register_sample({
            "domain": "pds",
            "signer": {"anon_id": "S-001", "region": "delhi"},
            "gloss_seq": ["rice"],
            "video": {"path": "raw/ISL-PDS-00001.mp4", "fps": 30, "duration_s": 2.0,
                      "source_kind": "recorded"},
            "keypoints": {"path": "keypoints/ISL-PDS-00001.json", "frame_count": 60},
            "_consent_status": "granted",
            "_consent_form_id": "CF-001",
            "_consent_usage": ["training"],
        })
        return s

    def _make_eligible(self, sample_id):
        self.store.add_label(sample_id, {"annotator": "A1", "gloss": "rice",
                                         "english_sentence": "I need rice."})
        self.store.add_label(sample_id, {"annotator": "A2", "gloss": "rice"})
        self.store.set_qa(sample_id, {"status": "passed", "reviewer": "R1"})

    def test_ineligible_until_consent_labels_qa(self):
        s = self._register_full()
        m = build_manifest(self.store, self.root)
        self.assertEqual(m["sample_count"], 0)  # consent pending, no labels, qa pending

    def test_eligible_flow_included_with_checksums(self):
        s = self._register_full()
        self._make_eligible(s["sample_id"])
        m = build_manifest(self.store, self.root)
        self.assertEqual(m["sample_count"], 1)
        rec = m["samples"][0]
        self.assertEqual(rec["sample_id"], "ISL-PDS-00001")
        self.assertEqual(rec["isl_gloss"], "rice")
        self.assertEqual(rec["english_sentence"], "I need rice.")
        self.assertEqual(len(rec["video"]["checksum_sha256"]), 64)
        self.assertEqual(len(rec["keypoints"]["checksum_sha256"]), 64)

    def test_ambiguous_consensus_excluded(self):
        s = self._register_full()
        self.store.add_label(s["sample_id"], {"annotator": "A1", "gloss": "rice"})
        self.store.add_label(s["sample_id"], {"annotator": "A2", "gloss": "wheat"})
        self.store.set_qa(s["sample_id"], {"status": "passed"})
        m = build_manifest(self.store, self.root)
        self.assertEqual(m["sample_count"], 0)

    def test_withdraw_after_eligible_excludes(self):
        s = self._register_full()
        self._make_eligible(s["sample_id"])
        self.store.withdraw("S-001")
        m = build_manifest(self.store, self.root)
        self.assertEqual(m["sample_count"], 0)

    def test_write_manifest_persists_and_reloads(self):
        s = self._register_full()
        self._make_eligible(s["sample_id"])
        out = write_manifest(self.store, self.root, version="v0.9.9-test")
        self.assertTrue(out.exists())
        self.assertTrue(out.name.startswith("bhashasetu-v0.9.9-test-"))
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["dataset_version"], "v0.9.9-test")
        self.assertEqual(data["sample_count"], 1)

    def test_domain_breakdown(self):
        s = self._register_full()
        self._make_eligible(s["sample_id"])
        m = build_manifest(self.store, self.root)
        self.assertEqual(m["by_domain"]["pds"], 1)
        self.assertEqual(m["by_domain"]["health"], 0)
        self.assertEqual(m["by_domain"]["legal"], 0)


if __name__ == "__main__":
    unittest.main()