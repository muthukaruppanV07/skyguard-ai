import numpy as np
import joblib
from pathlib import Path
from sklearn.preprocessing import RobustScaler
from backend.config import SCALER_PATH, MODEL_FEATURE_COLUMNS


class FeatureScaler:
    def __init__(self):
        self.scaler = RobustScaler()
        self.is_fitted = False
        self.feature_names = MODEL_FEATURE_COLUMNS

    def fit(self, X: np.ndarray):
        self.scaler.fit(X)
        self.is_fitted = True

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Scaler not fitted. Call fit() first.")
        return self.scaler.transform(X)

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        self.is_fitted = True
        return self.scaler.fit_transform(X)

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Scaler not fitted.")
        return self.scaler.inverse_transform(X)

    def save(self, path: Path = SCALER_PATH):
        joblib.dump(self.scaler, path)

    def load(self, path: Path = SCALER_PATH):
        self.scaler = joblib.load(path)
        self.is_fitted = True

    def get_params(self) -> dict:
        return {
            "center_": self.scaler.center_.tolist() if hasattr(self.scaler, "center_") else None,
            "scale_": self.scaler.scale_.tolist() if hasattr(self.scaler, "scale_") else None,
        }


def create_scaler() -> FeatureScaler:
    return FeatureScaler()