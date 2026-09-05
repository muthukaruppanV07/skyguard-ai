from __future__ import annotations

from typing import List

from app.providers.embeddings import EmbeddingService, cosine_similarity
from app.providers.vision import VisionService


class ObjectService:
    """Object/attribute extraction. Falls back to colour histograms + HOG."""

    def __init__(self, vision: VisionService):
        self.vision = vision
        self._yolo = None

    def analyze(self, image_bytes: bytes, description: str = "") -> dict:
        """Best-effort structured attribute extraction."""
        persons = self.vision.detect_persons(image_bytes)
        return {
            "persons_detected": len(persons),
            "persons": persons[:4],
            "objects": [],
            "attributes": self._attributes(image_bytes, description),
            "model": "YOLO" if self._yolo else "hog+colour-fallback",
        }

    def _attributes(self, image_bytes: bytes, description: str) -> List[str]:
        import cv2
        import numpy as np

        img = self.vision.decode(image_bytes)
        if img is None:
            return []

        # dominant colour buckets
        bgr = cv2.resize(img, (64, 64))
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0].mean()
        sat = hsv[:, :, 1].mean()
        val = hsv[:, :, 2].mean()

        colour = "unknown"
        if val < 50:
            colour = "black"
        elif sat < 25:
            colour = "white" if val > 200 else "grey"
        elif hue < 15 or hue > 170:
            colour = "red"
        elif hue < 35:
            colour = "yellow/orange"
        elif hue < 80:
            colour = "green"
        elif hue < 130:
            colour = "blue"
        else:
            colour = "purple/pink"

        attrs = [f"clothing_colour:{colour}"]
        tokens = [t.lower().strip(" ,.;:!?") for t in (description or "").split()]
        for token in tokens:
            if token in {"red", "blue", "green", "black", "white", "grey", "yellow", "jacket", "hoodie", "shirt", "coat", "jeans", "trousers", "backpack", "cap", "hat", "scarf", "glasses"}:
                attrs.append(f"token:{token}")
        return attrs


class Analyzer:
    """Orchestrates vision + embedding analysis for a single sighting image."""

    def __init__(self, settings, embeddings: EmbeddingService,
                 vision: VisionService, objects: ObjectService):
        self.settings = settings
        self.embeddings = embeddings
        self.vision = vision
        self.objects = objects

    def analyze(self, image_bytes: bytes, description: str = "") -> dict:
        quality = self.vision.quality(image_bytes)
        faces = self.vision.detect_faces(image_bytes)
        objects = self.objects.analyze(image_bytes, description)
        embedding = self.embeddings.image_embedding(image_bytes)

        return {
            "embedding": [round(float(x), 6) for x in embedding],
            "embedding_model": self.embeddings.mode,
            "quality": quality.to_dict(),
            "faces_detected": len(faces),
            "faces": faces,
            "objects": objects,
            "created_at": _now_iso(),
        }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
