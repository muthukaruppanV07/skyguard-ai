"""Unit tests for the JSONL label store (samples, labels, qa, consent)."""

import tempfile
import unittest
from pathlib import Path

from labeling.backend.store import LabelStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LabelStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _sample(self, domain="pds", signed=False):
        rec = {
            "domain": domain,
            "signer": {"anon_id": "S-001", "region": "delhi",
                       "native_sign_language": True},
            "gloss_seq": [],
        }
        if signed:
            rec.update({"_consent_status": "granted", "_consent_form_id": "CF-001"})
        return rec

    def test_register_and_id_sequence(self):
        a = self.store.register_sample(self._sample("pds"))
        b = self.store.register_sample(self._sample("pds"))
        self.assertEqual(a["sample_id"], "ISL-PDS-00001")
        self.assertEqual(b["sample_id"], "ISL-PDS-00002")
        self.assertEqual(a["status"], "registered")
        self.assertEqual(a["qa"]["status"], "pending")

    def test_domain_prefix(self):
        s = self.store.register_sample(self._sample("health"))
        self.assertTrue(s["sample_id"].startswith("ISL-HTH-"))

    def test_register_bad_domain_raises(self):
        with self.assertRaises(ValueError):
            self.store.register_sample({"domain": "nope"})

    def test_register_consent_and_withdraw(self):
        self.store.register_consent({"signer_id": "S-001", "form_id": "CF-1",
                                     "region": "delhi"})
        self.assertEqual(self.store.get_consent("S-001")["status"], "granted")
        s1 = self.store.register_sample(self._sample(signed=True))
        s2 = self.store.register_sample(self._sample(signed=True))
        impacted = self.store.withdraw("S-001")
        self.assertEqual(set(impacted), {s1["sample_id"], s2["sample_id"]})
        self.assertEqual(self.store.get_sample(s1["sample_id"])["status"], "withdrawn")
        self.assertEqual(self.store.get_consent("S-001")["status"], "withdrawn")

    def test_labels_latest_per_annotator(self):
        s = self.store.register_sample(self._sample())
        self.store.add_label(s["sample_id"], {"annotator": "A1", "gloss": "rice"})
        self.store.add_label(s["sample_id"], {"annotator": "A1", "gloss": "wheat"})
        self.store.add_label(s["sample_id"], {"annotator": "A2", "gloss": "wheat"})
        latest = self.store.latest_labels_for(s["sample_id"])
        self.assertEqual(len(latest), 2)
        wheat = [l for l in latest if l["annotator"] == "A1"][0]
        self.assertEqual(wheat["gloss"], "wheat")

    def test_add_label_requires_fields(self):
        s = self.store.register_sample(self._sample())
        with self.assertRaises(ValueError):
            self.store.add_label(s["sample_id"], {"annotator": "A1", "gloss": ""})

    def test_qa_lifecycle(self):
        s = self.store.register_sample(self._sample())
        row = self.store.set_qa(s["sample_id"], {"status": "passed", "reviewer": "R1"})
        sample = self.store.get_sample(s["sample_id"])
        self.assertEqual(sample["status"], "qa_pass")
        self.assertEqual(sample["qa"]["status"], "passed")
        self.assertEqual(row["reviewer"], "R1")

    def test_qa_bad_status_raises(self):
        s = self.store.register_sample(self._sample())
        with self.assertRaises(ValueError):
            self.store.set_qa(s["sample_id"], {"status": "maybe"})

    def test_stats_diversity(self):
        self.store.register_consent({"signer_id": "S-001", "region": "delhi",
                                     "age_group": "30-50", "gender": "f"})
        s = self.store.register_sample(self._sample(signed=True))
        s3 = self.store.register_sample({**self._sample("health", signed=True),
                                         "signer": {"anon_id": "S-002", "region": "chennai"}})
        stats = self.store.stats()
        self.assertEqual(stats["samples_total"], 2)
        self.assertEqual(stats["by_domain"]["pds"]["total"], 1)
        self.assertEqual(stats["signer_diversity"]["signers"], 2)
        self.assertEqual(sorted(stats["signer_diversity"]["regions"]),
                         ["chennai", "delhi"])

    def test_audit_trail_created(self):
        self.store.register_sample(self._sample())
        log = Path(self.tmp.name) / "annotations" / "audit.log"
        self.assertTrue(log.exists())
        self.assertIn("register_sample", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()