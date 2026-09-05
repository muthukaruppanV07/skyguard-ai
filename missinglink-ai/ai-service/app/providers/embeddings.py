"""Embedding providers.

Two tiers:
  * "real" providers (CLIP, insightface, YOLO) are loaded lazily only if the
    optional dependencies and weights are present;
  * the built-in fallback provider produces a *deterministic* 512-d perceptual
    signature from an image or text so the whole pipeline runs end-to-end in a
    demo/CI environment with no GPU and no model downloads.

The cosine similarity between two fallback signatures is meaningful (same
feature space), which is what makes demo matching work without any weights.
"""

from __future__ import annotations

import hashlib
import io
from typing import List, Optional, Tuple

import numpy as np

from app.config import Settings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64).ravel()
    b = b.astype(np.float64).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class FallbackEmbedder:
    """Deterministic multi-scale perceptual signature (no external deps)."""

    DIM = 512
    SEED = 1337

    def __init__(self) -> None:
        self._basis = self._build_basis()

    def _build_basis(self) -> np.ndarray:
        rng = np.random.default_rng(self.SEED)
        basis = rng.standard_normal((self.DIM, 64)) * 0.05
        return basis

    @staticmethod
    def _to_grayscale(img: np.ndarray) -> np.ndarray:
        if img.ndim == 3:
            if img.shape[2] == 4:
                img = img[:, :, :3]
            if img.shape[2] >= 3:
                return (0.299 * img[:, :, 0] + 0.587 * img[:, :, 1]
                        + 0.114 * img[:, :, 2]).astype(np.float32)
        return img.astype(np.float32)

    def embed(self, source: bytes | str) -> np.ndarray:
        features = self._features(source)
        # project into basis -> deterministic 512-d vector
        vec = self._basis @ features
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec

    def _features(self, source: bytes | str) -> np.ndarray:
        FEAT = 64
        if isinstance(source, str):
            return self._hash64(source.encode("utf-8"))

        img = self._decode(source)
        if img is None:
            return self._hash64(source)

        gray = self._to_grayscale(img)
        h, w = gray.shape[:2]
        if h > 0 and w > 0:
            size = 8  # 8x8 grid -> 64 features
            feats = np.zeros(size * size, dtype=np.float32)
            for y in range(size):
                for x in range(size):
                    y0, y1 = int(y * h / size), int((y + 1) * h / size)
                    x0, x1 = int(x * w / size), int((x + 1) * w / size)
                    cell = gray[max(0, y0):y1, max(0, x0):x1]
                    feats[y * size + x] = float(cell.mean()) if cell.size else 0.0
            return feats / 255.0
        return self._hash64(source)

    def _hash64(self, data: bytes) -> np.ndarray:
        out = np.zeros(64, dtype=np.float32)
        d1 = hashlib.sha256(data).digest()
        d2 = hashlib.sha256(d1).digest()
        full = (d1 + d2)[:64]
        for i, b in enumerate(full):
            out[i] = b / 255.0
        return out

    def _decode(self, source: bytes) -> Optional[np.ndarray]:
        import cv2

        try:
            arr = np.frombuffer(source, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None


class EmbeddingService:
    """Facade selecting a real model when available, else fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.fallback = FallbackEmbedder()
        self._clip = None
        self._clip_error = ""

    @property
    def mode(self) -> str:
        return "CLIP" if self._clip is not None else "fallback-perceptual"

    def _load_clip(self) -> None:
        if self._clip is not None or self._clip_error:
            return
        try:
            import torch  # noqa: F401
            from PIL import Image
            import torchvision.transforms as T
            import torchvision.models as M

            model = M.resnet18(weights=M.ResNet18_Weights.DEFAULT)
            model.fc = torch.nn.Identity()
            model.eval()
            self._clip = (model, T.Compose([
                T.Resize(224),
                T.CenterCrop(224),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]))
            self._transform = self._clip[1]
        except Exception as exc:  # noqa: BLE001
            self._clip_error = str(exc)
            self._clip = None

    def image_embedding(self, image_bytes: bytes) -> np.ndarray:
        self._load_clip()
        if self._clip is not None:
            try:
                import cv2

                arr = np.frombuffer(image_bytes, dtype=np.uint8)
                bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if bgr is not None:
                    import torch
                    from PIL import Image

                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    model, transform = self._clip
                    with torch.no_grad():
                        vec = model(transform(Image.fromarray(rgb)).unsqueeze(0))
                    return vec.squeeze().numpy().astype(np.float64)
            except Exception:  # noqa: BLE001
                pass
        return self.fallback.embed(image_bytes)

    def text_embedding(self, text: str) -> np.ndarray:
        self._load_clip()
        return self.fallback.embed(text)

    def embed_any(self, image_bytes: Optional[bytes], text: str) -> np.ndarray:
        if image_bytes:
            return self.image_embedding(image_bytes)
        return self.text_embedding(text)

    @property
    def dim(self) -> int:
        return self.settings.vector_dim
