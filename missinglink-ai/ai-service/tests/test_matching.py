import numpy as np
import pytest

from app.config import Settings
from app.providers.embeddings import EmbeddingService
from app.providers.vision import VisionService
from app.services.matching import MatchEngine


class FakeStore:
    def __init__(self, candidates):
        self._candidates = candidates

    def candidates(self):
        return self._candidates

    def candidates_by_embedding(self, _emb):
        return self._candidates


def _profile(case_id, text, lat, lng, status="ACTIVE"):
    return {
        "profile_id": case_id * 10,
        "case_id": case_id,
        "full_name": f"Person {case_id}",
        "status": status,
        "last_known_lat": lat,
        "last_known_lng": lng,
        "searchable_text": text,
        "clothing": "red jacket",
        "accessories": "backpack",
        "embedding": np.random.default_rng(case_id).standard_normal(512),
    }


def _engine(store, **overrides):
    settings = Settings(**overrides)
    emb = EmbeddingService(settings)
    return MatchEngine(settings, emb, VisionService(), store)


def test_ranking_prefers_geographically_nearby_profiles():
    store = FakeStore([
        _profile(1, "wearing a red jacket with a backpack", 12.91, 77.60),
        _profile(2, "wearing a green shirt walking along the coast", 28.60, 77.20),
    ])
    sighting = {
        "image_bytes": None,
        "description": "red jacket with a backpack near the lake",
        "lat": 12.9101, "lng": 77.6001,
        "captured_at": None,
        "attributes": ["clothing_colour:red"],
    }
    result = _engine(store).rank(sighting, store.candidates(), None)

    assert result["matches"], "expected at least one match"
    top = result["matches"][0]
    assert top["case_id"] == 1
    assert top["recommendation"]
    assert top["explanation"]


def test_weight_renormalisation_when_face_signal_absent():
    store = FakeStore([_profile(1, "red jacket backpack", 12.91, 77.60)])
    sighting = {
        "image_bytes": None,
        "description": "red jacket backpack",
        "lat": 12.91, "lng": 77.60,
        "captured_at": None,
        "attributes": ["clothing_colour:red", "token:backpack"],
    }
    result = _engine(store).rank(sighting, store.candidates(), None)
    top = result["matches"][0]
    assert top["signals"]["face"] is None
    assert "face" not in top["signal_weights"]
    # image absent too, but location + clothing + accessory + text are present
    assert 0.0 < top["match_score"] <= 1.0


def test_no_usable_signals_returns_zero():
    store = FakeStore([_profile(1, "xyzzy", 12.91, 77.60)])
    sighting = {
        "image_bytes": None,
        "description": "",
        "lat": None, "lng": None,
        "captured_at": None,
        "attributes": [],
    }
    result = _engine(store).rank(sighting, store.candidates(), None)
    assert result["matches"] == []
