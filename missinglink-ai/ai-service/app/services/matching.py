from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from app.config import Settings
from app.providers.embeddings import EmbeddingService, cosine_similarity
from app.providers.vision import VisionService
from app.vectorstore.pg import ProfileStore

logger = logging.getLogger(__name__)

SIGNAL_LABELS = {
    "face": "Facial similarity",
    "clothing": "Clothing similarity",
    "accessory": "Accessory match",
    "body": "Body build match",
    "image": "Overall image similarity",
    "location": "Location relevance",
    "time": "Time relevance",
    "text": "Narrative keywords",
}


class MatchEngine:
    def __init__(self, settings: Settings, embeddings: EmbeddingService,
                 vision: VisionService, store: ProfileStore):
        self.settings = settings
        self.embeddings = embeddings
        self.vision = vision
        self.store = store

    # ---------- signal scorers ------------------------------------------------
    def _image_sim(self, sighting_emb, profile_emb) -> Optional[float]:
        if sighting_emb is None or profile_emb is None:
            return None
        return max(0.0, cosine_similarity(sighting_emb, profile_emb))

    def _face_sim(self, image_bytes: Optional[bytes], profile_emb) -> Optional[float]:
        if not image_bytes or profile_emb is None:
            return None
        faces = self.vision.detect_faces(image_bytes)
        if not faces:
            return None
        import cv2
        img = self.vision.decode(image_bytes)
        if img is None:
            return None
        sims = []
        for f in faces[:3]:
            x, y, w, h = int(f["x"]), int(f["y"]), int(f["width"]), int(f["height"])
            x0, y0 = max(0, x - int(0.2 * w)), max(0, y - int(0.2 * h))
            x1 = min(img.shape[1], x + w + int(0.2 * w))
            y1 = min(img.shape[0], y + h + int(0.2 * h))
            crop = img[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            ok, buf = cv2.imencode(".jpg", crop)
            if not ok:
                continue
            emb = self.embeddings.image_embedding(buf.tobytes())
            sims.append(cosine_similarity(emb, profile_emb))
        return max(sims) if sims else None

    def _clothing_sim(self, sighting_attrs: List[str], profile_clothing: str) -> Optional[float]:
        prof = {t.lower() for t in (profile_clothing or "").split(",") if t.strip()}
        seen = set()
        for a in sighting_attrs:
            if a.startswith("clothing_colour:"):
                seen.add(a.split(":", 1)[1])
            elif a.startswith("token:"):
                tok = a.split(":", 1)[1]
                if any(tok in p for p in prof):
                    seen.add(tok)
        if not seen and not prof:
            return None
        if not prof:
            return 0.0
        return min(1.0, len(seen) / max(1, len(prof)) + 0.25)

    def _accessory_sim(self, sighting_attrs: List[str], profile_accessories: str) -> Optional[float]:
        prof = {t.lower() for t in (profile_accessories or "").split(",") if t.strip()}
        if not prof:
            return None
        seen = {a.split(":", 1)[1] for a in sighting_attrs if a.startswith("token:") and a.split(":", 1)[1] in prof}
        return min(1.0, len(seen) / len(prof))

    def _body_sim(self, sighting: dict, profile: dict) -> Optional[float]:
        return None

    def _location_relevance(self, lat, lng, profile, geo_radius_km: float) -> Optional[float]:
        if lat is None or profile.get("last_known_lat") is None:
            return None
        dist_km = _haversine_km(lat, lng, profile["last_known_lat"], profile["last_known_lng"])
        radius = geo_radius_km or 5.0
        # decay with distance relative to the configured geo radius
        return max(0.0, min(1.0, 1.0 - (dist_km / (3.0 * radius))))

    def _time_relevance(self, captured_at_iso, profile, time_decay_hours: float) -> Optional[float]:
        if captured_at_iso is None:
            return None
        from datetime import datetime, timezone
        try:
            captured = datetime.fromisoformat(captured_at_iso.replace("Z", "+00:00"))
        except ValueError:
            return None
        age_hours = max(0.0, (datetime.now(timezone.utc) - captured).total_seconds() / 3600.0)
        decay = time_decay_hours or 48.0
        return max(0.0, min(1.0, float(__import__("math").exp(-age_hours / decay))))

    def _text_sim(self, description: str, searchable_text: str) -> Optional[float]:
        if not description or not searchable_text:
            return None
        a = set(t.strip(" .,;:!?").lower() for t in description.split())
        b = set(t.strip(" .,;:!?").lower() for t in searchable_text.split())
        a = {t for t in a if len(t) > 3}
        b = {t for t in b if len(t) > 3}
        if not a or not b:
            return None
        inter = a & b
        if not inter:
            return 0.0
        return len(inter) / min(len(a), len(b))

    # ---------- ranking -------------------------------------------------------
    def rank(self, sighting: dict, candidates: List[dict],
             sighting_emb: Optional[np.ndarray],
             weights: Optional[dict] = None,
             geo_radius_km: float = 5.0,
             time_decay_hours: float = 48.0,
             min_score: float = 0.35) -> dict:
        image_bytes = sighting.get("image_bytes")
        attrs = sighting.get("attributes", [])

        results = []
        for prof in candidates:
            signals = {
                "face": self._face_sim(image_bytes, prof.get("embedding")),
                "clothing": self._clothing_sim(attrs, prof.get("clothing") or ""),
                "accessory": self._accessory_sim(attrs, prof.get("accessories") or ""),
                "body": self._body_sim(sighting, prof),
                "image": self._image_sim(sighting_emb, prof.get("embedding")),
                "location": self._location_relevance(
                    sighting.get("lat"), sighting.get("lng"), prof, geo_radius_km),
                "time": self._time_relevance(sighting.get("captured_at"), prof, time_decay_hours),
                "text": self._text_sim(sighting.get("description") or "", prof.get("searchable_text") or ""),
            }
            score, w, used = self._weighted(signals, weights)
            results.append({
                "case_id": prof["case_id"],
                "case_reference": prof.get("case_reference"),
                "profile_id": prof.get("profile_id"),
                "full_name": prof.get("full_name"),
                "status": prof.get("status"),
                "match_score": round(score, 4),
                "signals": {k: (None if v is None else round(v, 4)) for k, v in signals.items()},
                "signal_weights": {k: round(ww, 3) for k, ww in w.items() if k in used},
                "explanation": _explain(signals, w, used),
                "recommendation": _recommendation(score),
                "limitations": _limitations(signals),
            })

        results.sort(key=lambda r: r["match_score"], reverse=True)
        above = [r for r in results if r["match_score"] >= min_score]
        return {
            "threshold": min_score,
            "count": len(above),
            "matches": above,
            "model": {
                "embedding": self.embeddings.mode,
                "fallback_allowed": self.settings.fallback_allowed,
                "signal_weights_default": self.settings.weights,
            },
        }

    def _weighted(self, signals: dict, weights: Optional[dict] = None):
        order = ["face", "clothing", "accessory", "body", "image", "location", "time", "text"]
        base = dict(zip(order, self.settings.weights))
        if weights:
            for k in order:
                if k in weights:
                    try:
                        base[k] = float(weights[k])
                    except (TypeError, ValueError):
                        pass
        present = {k for k, v in signals.items() if v is not None}
        if not present:
            return 0.0, base, set()
        total = sum(base[k] for k in present)
        if total == 0:
            return 0.0, base, present
        score = sum(base[k] * signals[k] for k in present) / total
        return max(0.0, min(1.0, score)), base, present


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _explain(signals, weights, used) -> str:
    contrib = []
    for k in ["face", "clothing", "accessory", "body", "image", "location", "time", "text"]:
        if k not in used:
            continue
        v = signals[k]
        if v is None:
            continue
        kind = "supports" if v >= 0.6 else ("weakly supports" if v >= 0.4 else "does not support")
        contrib.append(f"{SIGNAL_LABELS[k]} {kind} the match ({v:.2f}, weight {weights[k]:.2f})")
    if not contrib:
        return "No usable signals were available for this comparison."
    return "; ".join(contrib) + "."


def _recommendation(score) -> str:
    if score >= 0.8:
        return "PRIORITY: high confidence match — escalate to case owner for confirmation."
    if score >= 0.6:
        return "Review: moderate confidence — ask witness to confirm details, contact case owner."
    if score >= 0.4:
        return "Possible lead: low confidence — include in queue, do not act alone."
    return "Unlikely match: no action recommended."


def _limitations(signals) -> List[str]:
    limits = []
    if signals.get("face") is None:
        limits.append("No clear face available — identity confidence relies on other signals.")
    if signals.get("image") is not None and signals.get("image") < 0.5:
        limits.append("Overall image similarity is weak; could be different lighting/angle.")
    if signals.get("location") is not None and signals["location"] < 0.3:
        limits.append("Sighting is far from the person's last-known location.")
    return limits
