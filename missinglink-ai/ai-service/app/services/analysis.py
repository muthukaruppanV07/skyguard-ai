from __future__ import annotations

import base64
import logging
import time
from typing import Optional

from app.config import Settings
from app.providers.embeddings import EmbeddingService
from app.providers.objects import Analyzer, ObjectService
from app.providers.vision import VisionService
from app.services.matching import MatchEngine
from app.vectorstore.pg import ProfileStore

logger = logging.getLogger(__name__)


def decode_image(image_b64: Optional[str]) -> Optional[bytes]:
    if not image_b64:
        return None
    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        return base64.b64decode(image_b64)
    except Exception:  # noqa: BLE001
        return None


def quality_score(quality: dict) -> float:
    if not quality:
        return 0.0
    score = 1.0
    if quality.get("is_blurry"):
        score -= 0.35
    if quality.get("too_dark"):
        score -= 0.35
    if quality.get("resolution") and quality["resolution"] < 200 * 200:
        score -= 0.2
    return round(max(0.05, min(1.0, score)), 3)


class AnalysisPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.embeddings = EmbeddingService(settings)
        self.vision = VisionService()
        self.objects = ObjectService(self.vision)
        self.analyzer = Analyzer(settings, self.embeddings, self.vision, self.objects)
        self.store = ProfileStore(settings)
        self.engine = MatchEngine(settings, self.embeddings, self.vision, self.store)

    def bootstrap(self) -> int:
        return self.store.bootstrap(self.embeddings)

    # -------------------------------------------------------------------------
    # Internal analysis helpers
    # -------------------------------------------------------------------------
    def _embed_and_attributes(self, image_bytes: Optional[bytes], description: str):
        if image_bytes is None:
            return None, [], None, 0
        attrs = self.objects.analyze(image_bytes, description).get("attributes", [])
        analysis = self.analyzer.analyze(image_bytes, description)
        embedding = self.embeddings.image_embedding(image_bytes)
        return attrs, analysis, embedding, len(analysis.get("faces", []))

    @staticmethod
    def _tags(attrs, prefix: str) -> list:
        return [a.split(":", 1)[1] for a in attrs if a.startswith(prefix + ":")]

    # -------------------------------------------------------------------------
    # Contract: POST /analyze/analyze-image  (multipart "file")
    # -------------------------------------------------------------------------
    def analyze_image_file(self, file_bytes: bytes) -> dict:
        started = time.time()
        if not file_bytes:
            raise ValueError("file is empty")
        embedding = self.embeddings.image_embedding(file_bytes)
        analysis = self.analyzer.analyze(file_bytes, "")
        quality = analysis["quality"]
        faces = analysis.get("faces", [])
        face_detected = len(faces) > 0
        face = faces[0] if faces else {"x": 0, "y": 0, "width": 0, "height": 0}
        attrs = analysis.get("objects", {}).get("attributes", [])

        objects = [
            {"label": "person", "confidence": 1.0,
             "bbox": [int(o["x"]), int(o["y"]), int(o["width"]), int(o["height"])]}
            for o in analysis.get("objects", {}).get("persons", [])
        ]

        return {
            "ok": True,
            "model": self.embeddings.mode,
            "qualityScore": quality_score(quality),
            "qualityFlags": quality.get("notes", []),
            "faceDetected": face_detected,
            "face": {
                "confidence": 0.0,
                "x": int(face["x"]), "y": int(face["y"]),
                "width": int(face["width"]), "height": int(face["height"]),
                "landmarks": [],
            },
            "objects": objects,
            "embedding": [round(float(x), 6) for x in embedding],
            "clothingTags": self._tags(attrs, "clothing_colour"),
            "accessoryTags": self._tags(attrs, "token"),
            "dimension": self.embeddings.dim,
            "processingTimeMs": int((time.time() - started) * 1000),
        }

    # -------------------------------------------------------------------------
    # Contract: POST /analyze/sighting  (JSON)
    # -------------------------------------------------------------------------
    def analyze_sighting(self, payload: dict) -> dict:
        image_b64 = payload.get("imageBase64")
        description = payload.get("description") or ""
        clothing = payload.get("clothing") or ""
        lat = payload.get("lat")
        lng = payload.get("lng")
        captured_at = payload.get("capturedAt")
        weights = payload.get("weights") or {}
        geo_radius_km = float(payload.get("geoRadiusKm") or 5.0)
        time_decay_hours = float(payload.get("timeDecayHours") or 48.0)
        min_score = float(payload.get("minOverallScore") or 0.35)

        image_bytes = decode_image(image_b64) if image_b64 else None
        attrs, analysis, embedding, n_faces = self._embed_and_attributes(image_bytes, description)
        if embedding is None:
            embedding = self.embeddings.text_embedding((description + " " + clothing).strip())

        candidates = self.store.candidates_by_embedding(embedding) if embedding is not None else self.store.candidates()

        sighting = {
            "image_bytes": image_bytes,
            "description": (description + " " + clothing).strip(),
            "lat": lat,
            "lng": lng,
            "captured_at": captured_at,
            "attributes": attrs or [],
        }

        ranking = self.engine.rank(
            sighting, candidates, embedding,
            weights=weights, geo_radius_km=geo_radius_km,
            time_decay_hours=time_decay_hours, min_score=min_score,
        )

        potential_matches = []
        for m in ranking["matches"]:
            signals = m.get("signals") or {}
            explanation = m.get("explanation")
            potential_matches.append({
                "caseId": m["case_id"],
                "caseReference": m.get("case_reference") or "",
                "overallScore": m["match_score"],
                "faceSimilarity": signals.get("face") or 0.0,
                "clothingSimilarity": signals.get("clothing") or 0.0,
                "accessorySimilarity": signals.get("accessory") or 0.0,
                "bodySimilarity": signals.get("body") or 0.0,
                "imageSimilarity": signals.get("image") or 0.0,
                "locationRelevance": signals.get("location") or 0.0,
                "timeRelevance": signals.get("time") or 0.0,
                "textSimilarity": signals.get("text") or 0.0,
                "explanation": [explanation] if explanation else [],
                "limitations": m.get("limitations") or [],
                "modelVersion": "v1.0.0",
            })

        quality = (analysis or {}).get("quality")
        warning = ""
        if n_faces == 0 and image_bytes is not None:
            warning = ("No clear face detected in the sighting image; "
                       "identity confidence relies on other signals only.")
        elif image_bytes is None:
            warning = "No image provided — ranking uses clothing/location/time/text signals only."

        return {
            "evidence": {
                "qualityScore": quality_score(quality),
                "qualityFlags": (quality or {}).get("notes", []),
                "faceDetected": n_faces > 0,
                "clothingTags": self._tags(attrs or [], "clothing_colour"),
                "accessoryTags": self._tags(attrs or [], "token"),
            },
            "potentialMatches": potential_matches,
            "imageEmbedding": [round(float(x), 6) for x in embedding] if embedding is not None else None,
            "model": self.embeddings.mode,
            "warning": warning,
        }

    # -------------------------------------------------------------------------
    # Contract: POST /v1/face-match  (multipart "file") — photo-of-a-person matching
    # -------------------------------------------------------------------------
    FACE_WEIGHTS = {
        "face": 0.55,
        "image": 0.15,
        "clothing": 0.10,
        "accessory": 0.05,
        "body": 0.05,
        "location": 0.05,
        "time": 0.05,
    }

    def face_match(self, file_bytes: bytes) -> dict:
        started = time.time()
        if not file_bytes:
            raise ValueError("file is empty")

        embedding = self.embeddings.image_embedding(file_bytes)
        analysis = self.analyzer.analyze(file_bytes, "")
        quality = analysis["quality"]
        faces = self.vision.detect_faces(file_bytes)
        face_detected = len(faces) > 0
        attrs = analysis.get("objects", {}).get("attributes", [])

        candidates = self.store.candidates_by_embedding(embedding)
        sighting = {
            "image_bytes": file_bytes,
            "description": "",
            "lat": None,
            "lng": None,
            "captured_at": None,
            "attributes": attrs or [],
        }
        ranking = self.engine.rank(
            sighting, candidates, embedding,
            weights=self.FACE_WEIGHTS,
            min_score=self.settings.min_match_score,
        )

        matches = []
        for m in ranking["matches"]:
            signals = m.get("signals") or {}
            matches.append({
                "caseId": m["case_id"],
                "caseReference": m.get("case_reference") or "",
                "fullName": m.get("full_name") or "Unknown",
                "status": m.get("status") or "",
                "matchScore": m["match_score"],
                "faceSimilarity": signals.get("face") or 0.0,
                "imageSimilarity": signals.get("image") or 0.0,
                "signalWeights": m.get("signal_weights") or {},
                "explanation": m.get("explanation") or "",
                "limitations": m.get("limitations") or [],
                "recommendation": m.get("recommendation") or "",
            })

        warning = ""
        if not face_detected:
            warning = ("No clear face detected — identity confidence relies on "
                       "overall image/appearance signals only.")

        return {
            "faceDetected": face_detected,
            "qualityScore": quality_score(quality),
            "qualityFlags": quality.get("notes", []),
            "matches": matches,
            "model": self.embeddings.mode,
            "threshold": self.settings.min_match_score,
            "processingTimeMs": int((time.time() - started) * 1000),
            "warning": warning,
        }

    # -------------------------------------------------------------------------
    # Convenience endpoint (base64 JSON) used by the test-suite
    # -------------------------------------------------------------------------
    def analyze_image(self, image_b64: str, description: str = "") -> dict:
        image_bytes = decode_image(image_b64)
        if image_bytes is None:
            raise ValueError("image is missing or not valid base64")
        return self.analyzer.analyze(image_bytes, description)
