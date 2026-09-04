from __future__ import annotations

import json
import logging
from typing import List, Optional

import numpy as np

from app.config import Settings

logger = logging.getLogger(__name__)

PROFILE_SQL = """
SELECT p.id AS profile_id, p.case_id, c.case_reference,
       CONCAT_WS(' ', c.first_name, c.last_name) AS full_name, c.status,
       c.last_known_lat, c.last_known_lng, c.last_known_at,
       p.searchable_text, p.clothing, p.accessories,
       p.embedding
FROM person_profiles p
JOIN missing_person_cases c ON c.id = p.case_id
WHERE c.status IN ('ACTIVE', 'CRITICAL')
"""


class ProfileStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.dsn = _dsn(settings.database_url)

    # ---------- connection helpers -------------------------------------------
    def _connect(self):
        import psycopg
        return psycopg.connect(self.dsn, connect_timeout=5)

    # ---------- public API ----------------------------------------------------
    def bootstrap(self, embedder) -> int:
        """Embed active profiles that have no embedding yet (text-signature)."""
        updated = 0
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT p.id, p.searchable_text
                        FROM person_profiles p
                        JOIN missing_person_cases c ON c.id = p.case_id
                        WHERE c.status IN ('ACTIVE', 'CRITICAL')
                          AND p.embedding IS NULL
                        LIMIT 500
                    """)
                    rows = cur.fetchall()
                    for pid, text in rows:
                        vec = embedder.text_embedding(text or f"profile-{pid}")
                        cur.execute(
                            "UPDATE person_profiles SET embedding = %s WHERE id = %s",
                            (_vec_literal(vec), pid),
                        )
                        updated += 1
                    conn.commit()
            if updated:
                logger.info("bootstrapped %d profile embeddings", updated)
        except Exception as exc:  # noqa: BLE001
            logger.warning("profile bootstrap skipped: %s", exc)
        return updated

    def candidates(self) -> List[dict]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(PROFILE_SQL)
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description]
                    out = []
                    for r in rows:
                        rec = dict(zip(cols, r))
                        rec["embedding"] = _parse_vec(rec.get("embedding"))
                        out.append(rec)
                    return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate load failed: %s", exc)
            return []

    def candidates_by_embedding(self, sighting_emb: Optional[np.ndarray]) -> List[dict]:
        """Prefer pgvector ANN search, fall back to in-memory cosine."""
        if sighting_emb is None:
            return self.candidates()
        try:
            lit = _vec_literal(sighting_emb)
            sql = PROFILE_SQL + "\nORDER BY p.embedding <=> " + lit + "\nLIMIT %s"
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (self.settings.match_k,))
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description]
                    out = []
                    for r in rows:
                        rec = dict(zip(cols, r))
                        rec["embedding"] = _parse_vec(rec.get("embedding"))
                        out.append(rec)
                    return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector search fell back to in-memory: %s", exc)
            cands = self.candidates()
            for c in cands:
                c["_dist"] = _cos(c.get("embedding"), sighting_emb)
            cands = [c for c in cands if c["_dist"] is not None]
            cands.sort(key=lambda c: c["_dist"])
            return cands[: self.settings.match_k]


def _dsn(url: str) -> str:
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql://", 1)
    return url


def _vec_literal(vec: np.ndarray) -> str:
    vals = ", ".join(f"{float(x):.6f}" for x in vec)
    return "[" + vals + "]"


def _parse_vec(value) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode()
        if isinstance(value, str):
            arr = json.loads(value)
        else:
            arr = value
        return np.asarray(arr, dtype=np.float64)
    except Exception:  # noqa: BLE001
        return None


def _cos(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> Optional[float]:
    if a is None or b is None:
        return None
    a = a.ravel()
    b = b.ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return None
    return 1.0 - float(np.dot(a, b) / (na * nb))
