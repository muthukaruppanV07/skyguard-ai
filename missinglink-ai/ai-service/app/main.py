from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile

from app.config import get_settings
from app.services.analysis import AnalysisPipeline

logger = logging.getLogger(__name__)

pipeline: AnalysisPipeline | None = None


def require_api_key(
    x_api_key: str = Header(default="", alias="X-API-Key"),
    x_ai_api_key: str = Header(default="", alias="X-AI-API-Key"),
):
    settings = get_settings()
    provided = x_api_key or x_ai_api_key
    if not settings.api_key or provided != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    settings = get_settings()
    pipeline = AnalysisPipeline(settings)
    if settings.bootstrap_on_start:
        try:
            pipeline.bootstrap()
        except Exception as exc:  # noqa: BLE001
            logger.warning("startup bootstrap failed: %s", exc)
    logger.info("AI pipeline ready (embedding=%s)", pipeline.embeddings.mode)
    yield


app = FastAPI(title="MissingLink AI Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/status")
def status():
    return {
        "embedding": pipeline.embeddings.mode,
        "vector_dim": pipeline.embeddings.dim,
        "fallback_allowed": pipeline.settings.fallback_allowed,
        "match_k": pipeline.settings.match_k,
        "weights": pipeline.settings.weights,
    }


# ---------------------------------------------------------------------------
# Backend-facing contract endpoints (called by Spring Boot AIGatewayService)
# ---------------------------------------------------------------------------
@app.post("/analyze/analyze-image")
def analyze_image(file: UploadFile, _: bool = Depends(require_api_key)):
    try:
        data = file.file.read()
        if not data:
            raise HTTPException(status_code=400, detail="file is empty")
        return pipeline.analyze_image_file(data)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/sighting")
def analyze_sighting(payload: dict, _: bool = Depends(require_api_key)):
    try:
        return pipeline.analyze_sighting(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/face-match")
def face_match(file: UploadFile, _: bool = Depends(require_api_key)):
    try:
        data = file.file.read()
        if not data:
            raise HTTPException(status_code=400, detail="file is empty")
        return pipeline.face_match(data)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/bootstrap")
def bootstrap(_: bool = Depends(require_api_key)):
    n = pipeline.bootstrap()
    return {"bootstrapped": n}
