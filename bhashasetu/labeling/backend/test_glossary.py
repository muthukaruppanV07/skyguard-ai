"""Unit tests for the glossary repository (loads real seed glossaries)."""

import json
import unittest
from pathlib import Path

from labeling.backend.glossary import GlossaryRepo

ROOT = Path(__file__).resolve().parents[2]
META = json.loads((ROOT / "data" / "glossaries" / "meta.json").read_text(encoding="utf-8"))


class GlossaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = GlossaryRepo(ROOT / "data" / "glossaries")

    def test_domains(self):
        self.assertEqual(self.repo.domains(), ["health", "legal", "pds"])

    def test_seed_sizes(self):
        self.assertGreaterEqual(len(self.repo.entries("pds")), 50)
        self.assertGreaterEqual(len(self.repo.entries("health")), 50)
        self.assertGreaterEqual(len(self.repo.entries("legal")), 50)

    def test_entries_conform_to_meta_categories(self):
        for domain in self.repo.domains():
            valid = set(META["domains"][domain]["categories"])
            for e in self.repo.entries(domain):
                self.assertIn(e["category"], valid, e["id"])
                self.assertNotEqual(e["sign_notes"].strip(), "")

    def test_find_exact(self):
        hit = self.repo.find("pds", "ration-card")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], "pds_001")

    def test_find_alias(self):
        self.assertIsNotNone(self.repo.find("pds", "pulse"))
        self.assertIsNotNone(self.repo.find("pds", "wheat"))

    def test_find_miss(self):
        self.assertIsNone(self.repo.find("pds", "zzz-does-not-exist"))

    def test_search(self):
        results = self.repo.search("pds", "card", limit=10)
        self.assertTrue(results)
        self.assertLessEqual(len(results), 10)
        ids = {r["id"] for r in results}
        self.assertIn("pds_001", ids)

    def test_suggest_prefix(self):
        hits = self.repo.suggest("health", "med")
        self.assertTrue(any(h["gloss"].startswith("medicine") for h in hits))

    def test_unknown_domain_raises(self):
        with self.assertRaises(KeyError):
            self.repo.entries("nope")


if __name__ == "__main__":
    unittest.main()