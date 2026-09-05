"""Unit tests for multi-annotator consensus logic."""

import unittest

from labeling.backend.consensus import compute_consensus, normalize_gloss


def _label(annotator, gloss, english="", confidence=0.8):
    return {"annotator": annotator, "gloss": gloss, "english_sentence": english,
            "confidence": confidence, "ts": "2026-08-19T00:00:00Z"}


class ConsensusTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_gloss("  Ration Card "), "ration-card")
        self.assertEqual(normalize_gloss("ration_card"), "ration-card")

    def test_needs_voting_below_two(self):
        c = compute_consensus([_label("A1", "ration-card")])
        self.assertEqual(c["status"], "needs_voting")
        self.assertEqual(c["annotator_count"], 1)

    def test_agreed(self):
        labels = [_label("A1", "ration-card", "I need my ration card."),
                  _label("A2", "ration-card")]
        c = compute_consensus(labels)
        self.assertEqual(c["status"], "agreed")
        self.assertEqual(c["gloss"], "ration-card")
        self.assertEqual(c["agreement"], 1.0)
        self.assertEqual(c["english_sentence"], "I need my ration card.")

    def test_ambiguous_when_anot_splits(self):
        labels = [_label("A1", "ration-card"),
                  _label("A2", "token")]
        c = compute_consensus(labels, threshold=0.6)
        self.assertEqual(c["status"], "ambiguous")
        self.assertLess(c["agreement"], 0.6)

    def test_english_taken_from_winning_gloss_voter(self):
        labels = [_label("A1", "token", "Where is the token counter?"),
                  _label("A2", "token", "Show me the token."),
                  _label("A3", "counter", "Counter please.")]
        c = compute_consensus(labels)
        self.assertEqual(c["gloss"], "token")
        self.assertAlmostEqual(c["agreement"], 2 / 3, places=3)
        self.assertIn(c["english_sentence"], ("Where is the token counter?",
                                              "Show me the token."))

    def test_empty(self):
        c = compute_consensus([])
        self.assertEqual(c["status"], "needs_voting")

    def test_whitespace_insensitive(self):
        labels = [_label("A1", "gas-cylinder"),
                  _label("A2", "Gas Cylinder")]
        self.assertEqual(compute_consensus(labels)["status"], "agreed")


if __name__ == "__main__":
    unittest.main()