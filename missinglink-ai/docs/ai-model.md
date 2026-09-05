# MISSINGLINK AI — AI Model & Vision Architecture

## 1. Position

The AI service generates **lead signals**, never identity verdicts. All output is
ranked into a *potential-match queue* that requires authorized human review.

## 2. Pipeline

```
INPUT IMAGE
  └─ ValidationProvider      (decodable, size, format)
      └─ QualityProvider     (blur, low-light, resolution) → quality_score + flags
          └─ FaceProvider    (detection → bbox + landmark; enrollment image optional)
              ├─ FaceEmbeddingProvider (128/512-d normalized vector)  [insightface | opencv | mock]
              └─ PersonClothingProvider (person bbox + clothing regions)
                  └─ ObjectProvider      (accessories, backpack, shoes)   [YOLO | mock]
                      └─ ImageEmbeddingProvider (512-d visual embedding)  [CLIP | histogram | mock]
                          └─ VectorStore   (pgvector HNSW cosine search)
                              └─ MatchingEngine (weighted multi-modal score)
                                  └─ ExplanationEngine (why + limitations)
                                      └─ RankedPotentialMatches (status AWAITING_REVIEW)
```

### Provider interfaces (replaceable)
Every model is behind a Provider abstraction:

```python
class FaceEmbeddingProvider(Protocol):
    def embed(self, image: np.ndarray, face_box: FaceBox | None) -> Vector
class ObjectDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[DetectedObject]
class ImageEmbeddingProvider(Protocol):
    def embed(self, image: np.ndarray) -> Vector
```

Selection logic (`get_face_provider()` etc.) tries, in order:
1. Best open-source model available (InsightFace → YOLO → CLIP) when installed + weights present
2. **Deterministic fallback providers** when `AI_FALLBACK_ALLOWED=true` (demo/dev)

Fallback providers are *cryptographic-feature* based (multi-scale luminance + edge
histograms + perceptual hash) — they are deterministic, work CPU-only, need no weights,
and are clearly labelled `model: "opencv-histogram-fallback/v1"` so operators know the
signal strength. **In production with real models, set `AI_FALLBACK_ALLOWED=false`.**

## 3. Multi-modal scoring

Overall score is a weighted sum, never face-only:

```
scores = {
  face:      cosine(image_emb, case_profile_emb)              w=0.35
  clothing:  clothing-region embedding cosine                  w=0.15
  accessory: object-set Jaccard over detected accessory tags   w=0.05
  body:      person bbox aspect-ratio similarity               w=0.05
  image:     whole-image embedding cosine                      w=0.10
  location:  1 - (dist_km / configured_radius_km)  (clipped)   w=0.15
  time:      exp(-Δt_hours / time_decay_hours)                 w=0.10
  text:      TF-IDF cosine over clothing/description tokens    w=0.05
}
overall = Σ w_i · s_i
```

- Weights are config-driven (`matching.weights` in config) so investigators can tune.
- Location/time relevance is only computed when the report and case have coordinates;
  otherwise those signals are excluded and the score is renormalized on the remaining
  signals (tracked in `limitations`).

## 4. Thresholds & honesty

- `MIN_OVERALL_SCORE` (default 0.55) below which no match is surfaced.
- Cosine floor for face similarity (0.35) to avoid noise.
- Every result ships `explanation` + `limitations` (see AI Explanation Panel).
- UI copy is enforced: **"POTENTIAL MATCH — HUMAN VERIFICATION REQUIRED"** is the only
  permissible framing; the API returns `warning` field, never "confirmed".

## 5. Explanation engine

Rules map signal strengths to human text:

| Signal | condition | explanation |
|---|---|---|
| face | ≥0.6 | "High visual similarity between sighting and case photo" |
| face | 0.35–0.6 | "Moderate face similarity (verify carefully)" |
| clothing | ≥0.5 | "Similar clothing color/pattern" |
| location | ≥0.7 | "Within configured geographic radius" |
| time | ≥0.6 | "Time interval is relevant" |
| text | ≥0.5 | "Description matches case profile" |

Limitations are derived from quality/analysis: low resolution, blur, occlusion,
lighting differences, missing GPS, timestamp uncertainty, fallback model in use.

## 6. Vector store

- PostgreSQL **pgvector** HNSW index (`vector_cosine_ops`), dimension 512.
- Queries done directly from the AI service over SQLAlchemy.
- `evidence_embeddings` stores per-evidence vectors; `person_profiles.embedding`
  stores the case reference vector (mean of authorized photo embeddings).

## 7. Model versioning

`model_versions` rows record: `face_model`, `embedding_model`, `detection_model`,
metrics (precision@k, latency). Every embedding and match references
`model_version_id` → enables A/B comparison in the Admin AI analytics dashboard.

## 8. Evaluation & benchmarks (tests)

- Embedding invariance: same-image → cosine ≈ 1.0; distinct images → lower.
- Fallback determinism: same input → same vector.
- Matching: synthetic positive/negative pairs; assert ranking order + no identity claims.
- Performance: p50/p95 latency budget (quality+detect+embed < 1.5 s CPU fallback).

## 9. Demo model behaviour

In demo/dev (default) the service runs with fallback providers so the entire stack
works without model weights. Everything downstream (vector search, ranking, UI,
verification workflow) is identical to production; only the embedding fidelity differs.
