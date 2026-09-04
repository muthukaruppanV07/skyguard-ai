import numpy as np
import pandas as pd
import joblib
import os
from typing import Dict, List, Optional, Tuple, Any
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from backend.config import settings
from backend.preprocessing.feature_engineer import EngineeredFeatures, FeatureEngineer


class IsolationForestDetector:
    def __init__(self, contamination: float = 0.05, n_estimators: int = 200, random_state: int = 42):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model: Optional[IsolationForest] = None
        self.scaler = StandardScaler()
        self.feature_names = EngineeredFeatures.feature_names()
        self.is_trained = False
        self.model_path = settings.ISOLATION_FOREST_PATH

    def train(self, features: np.ndarray, save: bool = True) -> Dict[str, Any]:
        self.scaler.fit(features)
        scaled_features = self.scaler.transform(features)

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
            verbose=0
        )
        self.model.fit(scaled_features)
        self.is_trained = True

        scores = self.model.score_samples(scaled_features)
        anomaly_scores = self._convert_to_anomaly_score(scores)

        if save:
            self.save()

        return {
            "n_samples": len(features),
            "anomaly_ratio": np.mean(anomaly_scores > 50),
            "mean_score": np.mean(anomaly_scores),
            "std_score": np.std(anomaly_scores)
        }

    def predict(self, features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Call train() first or load a saved model.")

        scaled_features = self.scaler.transform(features)
        raw_scores = self.model.score_samples(scaled_features)
        anomaly_scores = self._convert_to_anomaly_score(raw_scores)
        predictions = (anomaly_scores > 50).astype(int)

        return predictions, anomaly_scores

    def predict_single(self, feature_vector: np.ndarray) -> Tuple[int, float]:
        preds, scores = self.predict(feature_vector.reshape(1, -1))
        return int(preds[0]), float(scores[0])

    def _convert_to_anomaly_score(self, raw_scores: np.ndarray) -> np.ndarray:
        min_score = np.min(raw_scores)
        max_score = np.max(raw_scores)
        if max_score == min_score:
            return np.full_like(raw_scores, 50.0)
        normalized = (raw_scores - min_score) / (max_score - min_score)
        anomaly_scores = (1 - normalized) * 100
        return anomaly_scores

    def get_feature_importance(self) -> Dict[str, float]:
        if not self.is_trained or self.model is None:
            return {}

        importances = {}
        for tree in self.model.estimators_:
            tree_importance = tree.feature_importances_
            for i, name in enumerate(self.feature_names):
                if name not in importances:
                    importances[name] = 0.0
                importances[name] += tree_importance[i]

        for name in importances:
            importances[name] /= self.n_estimators

        return dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

    def save(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state
        }, self.model_path)

    def load(self) -> bool:
        if not os.path.exists(self.model_path):
            return False

        data = joblib.load(self.model_path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.feature_names = data["feature_names"]
        self.contamination = data["contamination"]
        self.n_estimators = data["n_estimators"]
        self.random_state = data["random_state"]
        self.is_trained = True
        return True


def train_isolation_forest_from_historical(days: int = 30) -> IsolationForestDetector:
    from backend.simulation.aws_simulator import create_historical_data
    from backend.preprocessing.feature_engineer import FeatureEngineer

    print(f"Generating {days} days of historical data...")
    df = create_historical_data(days=days, interval_minutes=5)

    print("Engineering features...")
    engineer = FeatureEngineer()
    feature_df = engineer.engineer_batch(df)

    feature_cols = EngineeredFeatures.feature_names()
    X = feature_df[feature_cols].values

    print(f"Training Isolation Forest on {len(X)} samples with {X.shape[1]} features...")
    detector = IsolationForestDetector(contamination=0.05)
    results = detector.train(X)

    print(f"Training complete. Anomaly ratio: {results['anomaly_ratio']:.2%}")
    return detector