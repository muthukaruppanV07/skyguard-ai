"""Glossary repository: loads + validates domain vocabularies from JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

GLOSSARY_FILES = {"pds": "pds.json", "health": "health.json", "legal": "legal.json"}


class GlossaryRepo:
    def __init__(self, gloss_dir: Path):
        self.gloss_dir = Path(gloss_dir)
        self._cache: dict[str, dict] = {}

    def _load(self, domain: str) -> dict:
        if domain not in GLOSSARY_FILES:
            raise KeyError(f"unknown domain {domain!r}")
        if domain not in self._cache:
            path = self.gloss_dir / GLOSSARY_FILES[domain]
            self._cache[domain] = json.loads(path.read_text(encoding="utf-8"))
        return self._cache[domain]

    def domains(self) -> list[str]:
        return sorted(GLOSSARY_FILES)

    def entries(self, domain: str) -> list[dict]:
        return self._load(domain)["glosses"]

    def entry_by_id(self, domain: str, gloss_id: str) -> dict | None:
        for e in self.entries(domain):
            if e["id"] == gloss_id:
                return e
        return None

    def find(self, domain: str, gloss: str) -> dict | None:
        """Exact (normalized) gloss search across the domain vocabulary."""
        target = re.sub(r"\s+", "-", gloss.strip().lower()).replace("_", "-")
        for e in self.entries(domain):
            if e["gloss"].strip().lower() == target:
                return e
            if any(a.strip().lower().replace(" ", "-") == target for a in e["aliases"]):
                return e
        return None

    def search(self, domain: str, query: str, limit: int = 25) -> list[dict]:
        q = re.sub(r"\s+", "-", query.strip().lower()).replace("_", "-")
        if not q:
            return []
        scored = []
        for e in self.entries(domain):
            hay = {e["gloss"].lower(), *[a.lower() for a in e["aliases"]],
                   e["english"].lower(), e["id"]}
            if q in e["gloss"].lower():
                score = 0
            elif any(q in h for h in hay):
                score = 1
            else:
                continue
            scored.append((score, e))
        scored.sort(key=lambda t: (t[0], t[1]["id"]))
        return [e for _, e in scored[:limit]]

    def suggest(self, domain: str, query: str, limit: int = 10) -> list[dict]:
        """Autocomplete: prefix/substring matches on gloss + aliases."""
        q = query.strip().lower().replace(" ", "-")
        hits = []
        for e in self.entries(domain):
            names = [e["gloss"].lower()] + [a.lower() for a in e["aliases"]]
            if any(q in name for name in names):
                hits.append(e)
        return hits[:limit]