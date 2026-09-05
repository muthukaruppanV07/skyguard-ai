"""Multi-annotator consensus over gloss labels.

Pure functions: no I/O, easy to unit-test. Used by the labeling API and the
manifest exporter.

Rules (small-data friendly):
- One vote per annotator (most recent wins, see ``latest_labels_for``).
- Glosses are normalized (lowercase, inner whitespace collapsed) before voting so
  'ration-ration' vs 'Ration card' count differently — the labeler must pick from
  the glossary vocabulary; free text is preserved on the label but a fuzzy match
  against the glossary is reported for QA.
- Status:
    needs_voting  -> fewer than 2 annotators
    agreed        -> >=2 annotators and top-vote share >= threshold
    ambiguous     -> >=2 annotators and top-vote share < threshold (needs more voters)
"""

from __future__ import annotations

AGREEMENT_THRESHOLD = 0.6
MIN_ANNOTATORS = 2


def normalize_gloss(gloss: str) -> str:
    g = str(gloss).strip().lower()
    g = "-".join(g.split())
    g = g.replace("_", "-")
    return g


def compute_consensus(labels: list[dict], threshold: float = AGREEMENT_THRESHOLD) -> dict:
    """labels: list of label dicts (already latest-per-annotator)."""
    if not labels:
        return {"gloss": "", "english_sentence": "", "annotator_count": 0,
                "agreement": 0.0, "threshold": threshold, "status": "needs_voting"}

    votes: dict[str, int] = {}
    for lab in labels:
        key = normalize_gloss(lab.get("gloss", ""))
        if key:
            votes[key] = votes.get(key, 0) + 1

    n = len(labels)
    top = max(votes.items(), key=lambda kv: kv[1])
    agreement = top[1] / n if n else 0.0

    if n < MIN_ANNOTATORS:
        status = "needs_voting"
    elif agreement >= threshold:
        status = "agreed"
    else:
        status = "ambiguous"

    english = ""
    for lab in labels:  # pick english from a label that voted for the winning gloss
        if normalize_gloss(lab.get("gloss", "")) == top[0] and lab.get("english_sentence"):
            english = lab["english_sentence"]
            break

    return {
        "gloss": top[0],
        "english_sentence": english,
        "annotator_count": n,
        "agreement": round(agreement, 3),
        "threshold": threshold,
        "status": status,
        "votes": [{"gloss": k, "votes": v} for k, v in sorted(votes.items(), key=lambda kv: -kv[1])],
    }


def attach_consensus_meta(sample: dict, labels: list[dict]) -> dict:
    """Sample view helper: enrich a sample record with consensus + glossary match."""
    sample = dict(sample)
    latest = labels
    sample["latest_labels"] = latest
    sample["consensus"] = compute_consensus(latest)
    return sample