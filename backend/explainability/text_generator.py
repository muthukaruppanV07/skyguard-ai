from typing import Dict, Any, List
from backend.explainability.shap_explainer import ExplanationGenerator, create_explanation_generator
from backend.config import settings


class TextExplainer:
    def __init__(self):
        self.generator = create_explanation_generator()

    def generate_explanation(
        self,
        anomaly_data: Dict[str, Any],
        shap_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        root_cause = anomaly_data.get("root_cause", "NORMAL")
        current = {
            "temperature": anomaly_data.get("observed_temp", 0),
            "pressure": anomaly_data.get("observed_pressure", 0),
            "humidity": anomaly_data.get("observed_humidity", 0),
        }
        history = anomaly_data.get("history", [])
        scores = anomaly_data.get("scores", {})
        confidence = anomaly_data.get("confidence", 0.9)

        neighbor_context = self._build_spatial_context(anomaly_data)

        explanation_text = self.generator.generate(
            root_cause=root_cause,
            current=current,
            history=history,
            scores=scores,
            neighbor_context=neighbor_context,
            confidence=confidence,
        )

        contributing_factors = self._extract_factors(anomaly_data, shap_data)

        return {
            "explanation": explanation_text,
            "contributing_factors": contributing_factors,
            "confidence": confidence,
            "root_cause": root_cause,
        }

    def _build_spatial_context(self, anomaly_data: Dict) -> str:
        spatial_details = anomaly_data.get("spatial_details", {})
        neighbors = spatial_details.get("details", {}).get("neighbors_used", [])
        
        if not neighbors:
            return "Neighboring stations not available for comparison."
        
        return f"Nearby stations ({', '.join(neighbors[:3])}) show normal readings."

    def _extract_factors(
        self,
        anomaly_data: Dict,
        shap_data: Dict = None,
    ) -> List[Dict[str, Any]]:
        factors = []
        
        components = anomaly_data.get("scores", {}).get("components", {})
        for name, score in components.items():
            if score > 30:
                factors.append({
                    "factor": name.replace("_", " ").title(),
                    "score": round(score, 1),
                    "impact": "high" if score > 70 else "medium" if score > 40 else "low",
                })

        if shap_data and shap_data.get("top_features"):
            for feat in shap_data["top_features"][:3]:
                factors.append({
                    "factor": f"ML Feature: {feat['feature']}",
                    "score": round(feat['importance'] * 100, 1),
                    "impact": "high" if feat['importance'] > 0.1 else "medium",
                })

        factors.sort(key=lambda x: x["score"], reverse=True)
        return factors[:10]


def create_text_explainer() -> TextExplainer:
    return TextExplainer()