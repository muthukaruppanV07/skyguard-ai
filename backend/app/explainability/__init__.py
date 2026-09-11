"""SHAP + human-readable explanations."""

from backend.app.explainability.explainer import (
    ATTRIBUTION_METHOD,
    SHAP_AVAILABLE,
    Explanation,
    build_explanation,
    compact_explanation,
    detector_contributions,
    model_feature_contributions,
)

__all__ = [
    "ATTRIBUTION_METHOD",
    "SHAP_AVAILABLE",
    "Explanation",
    "build_explanation",
    "compact_explanation",
    "detector_contributions",
    "model_feature_contributions",
]
