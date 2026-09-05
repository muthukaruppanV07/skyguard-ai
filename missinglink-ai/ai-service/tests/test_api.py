import base64

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app


def _tiny_png() -> bytes:
    img = np.full((64, 64, 3), (120, 90, 60), dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (54, 54), (200, 200, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _auth():
    return {"X-AI-API-Key": "change-me-ai-key"}


def test_health():
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_api_key_required():
    with TestClient(app) as client:
        res = client.post("/analyze/analyze-image", files={"file": ("a.png", _tiny_png(), "image/png")})
        assert res.status_code == 401


def test_analyze_image_contract():
    with TestClient(app) as client:
        res = client.post(
            "/analyze/analyze-image",
            files={"file": ("a.png", _tiny_png(), "image/png")},
            headers=_auth(),
        )
        assert res.status_code == 200
        body = res.json()
        # exact field set the Spring Boot AIGatewayService expects
        assert body["ok"] is True
        assert "model" in body
        assert 0.0 <= body["qualityScore"] <= 1.0
        assert isinstance(body["qualityFlags"], list)
        assert isinstance(body["faceDetected"], bool)
        assert set(body["face"]) == {"confidence", "x", "y", "width", "height", "landmarks"}
        assert isinstance(body["objects"], list)
        assert len(body["embedding"]) == 512
        assert isinstance(body["clothingTags"], list)
        assert isinstance(body["accessoryTags"], list)
        assert body["dimension"] == 512
        assert body["processingTimeMs"] >= 0


def test_empty_file_rejected():
    with TestClient(app) as client:
        res = client.post(
            "/analyze/analyze-image",
            files={"file": ("empty.png", b"", "image/png")},
            headers=_auth(),
        )
        assert res.status_code == 400


def test_face_match_contract():
    with TestClient(app) as client:
        res = client.post(
            "/v1/face-match",
            files={"file": ("a.png", _tiny_png(), "image/png")},
            headers=_auth(),
        )
        assert res.status_code == 200
        body = res.json()
        assert set(body) == {
            "faceDetected", "qualityScore", "qualityFlags", "matches",
            "model", "threshold", "processingTimeMs", "warning",
        }
        assert isinstance(body["faceDetected"], bool)
        assert 0.0 <= body["qualityScore"] <= 1.0
        assert isinstance(body["matches"], list)
        assert isinstance(body["warning"], str)
        if body["matches"]:
            m = body["matches"][0]
            assert set(m) == {
                "caseId", "caseReference", "fullName", "status", "matchScore",
                "faceSimilarity", "imageSimilarity", "signalWeights",
                "explanation", "limitations", "recommendation",
            }


def test_face_match_requires_key():
    with TestClient(app) as client:
        res = client.post("/v1/face-match", files={"file": ("a.png", _tiny_png(), "image/png")})
        assert res.status_code == 401


def test_analyze_sighting_contract():
    """Contract test mirroring the Spring Boot AnalyzeSightingRequest JSON."""
    with TestClient(app) as client:
        res = client.post(
            "/analyze/sighting",
            headers=_auth(),
            json={
                "lat": 12.9756,
                "lng": 77.6041,
                "capturedAt": "2026-08-09T10:00:00Z",
                "description": "child wearing a blue jacket with a black backpack",
                "clothing": "blue jacket",
                "imageBase64": base64.b64encode(_tiny_png()).decode(),
                "weights": {"face": 0.30, "clothing": 0.20, "image": 0.15,
                            "location": 0.05, "time": 0.05, "text": 0.05},
                "geoRadiusKm": 5.0,
                "timeDecayHours": 48.0,
                "minOverallScore": 0.35,
            },
        )
        assert res.status_code == 200
        body = res.json()
        # exact field set the Spring Boot AnalyzeSightingResponse expects
        assert set(body) == {"evidence", "potentialMatches", "imageEmbedding", "model", "warning"}
        ev = body["evidence"]
        assert set(ev) == {"qualityScore", "qualityFlags", "faceDetected", "clothingTags", "accessoryTags"}
        assert isinstance(body["potentialMatches"], list)
        if body["potentialMatches"]:
            m = body["potentialMatches"][0]
            assert set(m) == {
                "caseId", "caseReference", "overallScore", "faceSimilarity", "clothingSimilarity",
                "accessorySimilarity", "bodySimilarity", "imageSimilarity", "locationRelevance",
                "timeRelevance", "textSimilarity", "explanation", "limitations", "modelVersion",
            }
        assert body["model"]
        assert isinstance(body["warning"], str)
