"""Unit tests for the bulk video importer (validation, idempotency, failures)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from labeling.backend.store import LabelStore
from labeling.scripts import import_videos

ROOT = Path(__file__).resolve().parents[2]


class ImportVideosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # import_videos reads glossary meta from the real seed dir for validation
        shutil.copytree(ROOT / "data" / "glossaries",
                        self.root / "glossaries")
        (self.root / "raw" / "uploads").mkdir(parents=True)
        self.store = LabelStore(self.root)
        self.store.register_consent({"signer_id": "S-001", "form_id": "CF-1",
                                     "region": "delhi", "status": "granted"})
        self.vid = self.root / "raw" / "uploads" / "clip-a.mp4"
        self.vid.write_bytes(b"FAKEMP4")

    def tearDown(self):
        self.tmp.cleanup()

    def _csv(self, rows):
        p = self.root / "upload.csv"
        import csv
        with open(p, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=import_videos.CSV_FIELDNAMES)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        return p

    def _row(self, **over):
        row = {"domain": "pds", "signer_id": "S-001", "region": "delhi",
               "video_path": "raw/uploads/clip-a.mp4", "keypoints_path": "",
               "gloss": "ration-card", "consent_form_id": "CF-1",
               "consent_status": "granted", "source_kind": "self-recorded",
               "source_url": "", "notes": ""}
        row.update(over)
        return row

    def test_import_and_idempotency(self):
        csv_file = self._csv([self._row()])
        created, failed, skipped = import_videos.import_rows(self.store, csv_file, self.root)
        self.assertEqual(created, ["ISL-PDS-00001"])
        self.assertEqual(failed, [])
        self.assertEqual(skipped, [])

        sample = self.store.get_sample("ISL-PDS-00001")
        self.assertEqual(sample["video"]["path"], "raw/uploads/clip-a.mp4")
        self.assertEqual(sample["consent"]["status"], "granted")
        self.assertEqual(sample["gloss_seq"], ["ration", "card"])

        created2, failed2, skipped2 = import_videos.import_rows(self.store, csv_file, self.root)
        self.assertEqual(created2, [])
        self.assertEqual(failed2, [])
        self.assertEqual(skipped2, [("raw/uploads/clip-a.mp4", "already registered")])
        self.assertEqual(len(self.store.all_samples()), 1)

    def test_missing_consent_fails(self):
        csv_file = self._csv([self._row(signer_id="S-999")])
        created, failed, skipped = import_videos.import_rows(self.store, csv_file, self.root)
        self.assertEqual(created, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("no consent record", failed[0][1])

    def test_bad_region_fails(self):
        csv_file = self._csv([self._row(region="atlantis")])
        created, failed, skipped = import_videos.import_rows(self.store, csv_file, self.root)
        self.assertEqual(created, [])
        self.assertIn("region invalid", failed[0][1])

    def test_missing_video_fails(self):
        csv_file = self._csv([self._row(video_path="raw/uploads/ghost.mp4")])
        created, failed, skipped = import_videos.import_rows(self.store, csv_file, self.root)
        self.assertEqual(created, [])
        self.assertIn("video file missing", failed[0][1])

    def test_consent_form_mismatch_fails(self):
        csv_file = self._csv([self._row(consent_form_id="WRONG")])
        created, failed, skipped = import_videos.import_rows(self.store, csv_file, self.root)
        self.assertEqual(created, [])
        self.assertIn("consent_form_id does not match", failed[0][1])


if __name__ == "__main__":
    unittest.main()