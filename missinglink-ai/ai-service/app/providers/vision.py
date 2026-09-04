"""Image quality + face detection.

Uses OpenCV only (ships with the container). Face detection uses the bundled
Haar cascade; real deployments should swap in insightface/RetinaFace.
"""

from __future__ import annotations

import io
from typing import List, Optional

import cv2
import numpy as np


class QualityReport:
    def __init__(self, *, sharpness: float, brightness: float, resolution: int,
                 is_blurry: bool, too_dark: bool, is_clear: bool, notes: List[str]):
        self.sharpness = sharpness
        self.brightness = brightness
        self.resolution = resolution
        self.is_blurry = is_blurry
        self.too_dark = too_dark
        self.is_clear = is_clear
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "sharpness": round(self.sharpness, 4),
            "brightness": round(self.brightness, 2),
            "resolution": self.resolution,
            "is_blurry": self.is_blurry,
            "too_dark": self.too_dark,
            "is_clear": self.is_clear,
            "notes": self.notes,
        }


class VisionService:
    def __init__(self, cascade_path: Optional[str] = None):
        # OpenCV's CascadeClassifier/HOG descriptors segfault with a native
        # access violation when called from any non-main thread — but uvicorn
        # and Starlette TestClient run sync endpoints in worker threads. We
        # therefore avoid those detectors entirely and use NumPy heuristics.
        del cascade_path

    def decode(self, image_bytes: bytes) -> Optional[np.ndarray]:
        try:
            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:  # noqa: BLE001
            return None

    def quality(self, image_bytes: bytes) -> QualityReport:
        img = self.decode(image_bytes)
        if img is None:
            return QualityReport(
                sharpness=0.0, brightness=0.0, resolution=0,
                is_blurry=True, too_dark=True, is_clear=False,
                notes=["Unable to decode image; treat with caution."])

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        resolution = h * w

        is_blurry = laplacian_var < 60.0
        too_dark = brightness < 45.0
        is_clear = not is_blurry and not too_dark and resolution >= 200 * 200

        notes = []
        if is_blurry:
            notes.append("Blur detected; facial comparison may be unreliable.")
        if too_dark:
            notes.append("Image is very dark; detail is limited.")
        if resolution < 200 * 200:
            notes.append("Low resolution; identity confidence reduced.")

        return QualityReport(
            sharpness=laplacian_var, brightness=brightness, resolution=resolution,
            is_blurry=is_blurry, too_dark=too_dark, is_clear=is_clear, notes=notes)

    def detect_faces(self, image_bytes: bytes) -> List[dict]:
        """Crash-proof face detection via skin-colour blob heuristic.

        OpenCV's haar cascade segfaults on non-main threads on this platform,
        so we find warm (skin-toned) blobs instead. Swap in insightface /
        RetinaFace for a production detector.
        """
        img = self.decode(image_bytes)
        if img is None:
            return []
        try:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.int16)
        except Exception:  # noqa: BLE001
            return []
        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]
        skin = ((h <= 20) | (h >= 168)) & (s >= 40) & (s <= 200) & (v >= 50)
        blobs = _largest_blob_bboxes(skin, limit=3, min_area_pct=0.002, max_area_pct=0.9)
        return [{"x": x, "y": y, "width": w, "height": h} for (x, y, w, h) in blobs]

    def detect_persons(self, image_bytes: bytes) -> List[dict]:
        """Crash-proof person detection via a foreground-blob heuristic."""
        img = self.decode(image_bytes)
        if img is None:
            return []
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception:  # noqa: BLE001
            return []
        fg = (gray > 200) | (gray < 40)
        blobs = _largest_blob_bboxes(fg, limit=4, min_area_pct=0.005, max_area_pct=0.85)
        return [{"x": x, "y": y, "width": w, "height": h} for (x, y, w, h) in blobs]


def _largest_blob_bboxes(mask: np.ndarray, limit: int,
                         min_area_pct: float, max_area_pct: float) -> List[tuple]:
    """Top-N connected blobs of a boolean mask, back-projected to pixels.

    Pure Python (BFS on a downsampled grid) — deliberately avoids OpenCV's
    connectedComponents / detector stack, which is unsafe off the main thread
    on this platform.
    """
    h, w = mask.shape
    if h == 0 or w == 0:
        return []
    gw, gh = 48, 48
    step_y = max(1, round(h / gh))
    step_x = max(1, round(w / gw))
    grid = mask[::step_y, ::step_x]
    gh2, gw2 = grid.shape
    visited = np.zeros((gh2, gw2), dtype=bool)
    blobs = []
    total = float(gw2 * gh2)
    for y in range(gh2):
        for x in range(gw2):
            if visited[y, x] or not grid[y, x]:
                continue
            queue = [(x, y)]
            visited[y, x] = True
            minx = maxx = x
            miny = maxy = y
            area = 0
            while queue:
                cx, cy = queue.pop()
                area += 1
                if cx < minx:
                    minx = cx
                elif cx > maxx:
                    maxx = cx
                if cy < miny:
                    miny = cy
                elif cy > maxy:
                    maxy = cy
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < gw2 and 0 <= ny < gh2 and not visited[ny, nx] and grid[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))
            bw = (maxx + 1) * step_x - minx * step_x
            bh = (maxy + 1) * step_y - miny * step_y
            if bw <= 0 or bh <= 0:
                continue
            area_pct = area / total
            if area_pct < min_area_pct or area_pct > max_area_pct:
                continue
            if not (0.25 <= bw / bh <= 6.0):
                continue
            blobs.append((minx * step_x, miny * step_y, bw, bh))
    blobs.sort(key=lambda b: b[2] * b[3], reverse=True)
    return blobs[:limit]
