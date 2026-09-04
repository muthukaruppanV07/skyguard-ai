import numpy as np
import joblib
from pathlib import Path
from typing import Optional, Dict, Any
from sklearn.ensemble import IsolationForest
from backend.config import settings, ISOLATION_FOREST_PATH


class IsolationForestModel:
    def __init__(self):
        self.model: Optional[IsolationForest] = None
        self.is_fitted = False
        self.model_path = ISOLATION_FOREST_PATH

    def build_model(self) -> IsolationForest:
        return IsolationForest(
            n_estimators=settings.IF_N_ESTIMATORS,
            contamination=settings.IF_CONTAMINATION,
            max_samples=settings.IF_MAX_SAMPLES,
            random_state=settings.IF_RANDOM_STATE,
            n_jobs=-1,
        )

    def fit(self, X: np.ndarray):
        self.model = self.build_model()
        self.model.fit(X)
        self.is_fitted = True

    def predict_score(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        scores = self.model.decision_function(X)
        anomaly_scores = -scores
        
        min_score = anomaly_scores.min()
        max_score = anomaly_scores.max()
        if max_score > min_score:
            normalized = (anomaly_scores - min_score) / (max_score - min_score)
        else:
            normalized = np.zeros_like(anomaly_scores)
        
        return normalized * 100

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            raise ValueError("Model not fitted.")
        return self.model.predict(X)

    def save(self, path: Optional[Path] = None):
        if self.model is not None:
            joblib.dump(self.model, path or self.model_path)

    def load(self, path: Optional[Path] = None):
        self.model = joblib.load(path or self.model_path)
        self.is_fitted = True

    def get_params(self) -> Dict[str, Any]:
        if self.model:
            return self.model.get_params()
        return {}


def create_isolation_forest() -> IsolationForestModel:
    return IsolationForestModel()