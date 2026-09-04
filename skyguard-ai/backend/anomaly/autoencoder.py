import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import os
from typing import Dict, List, Optional, Tuple, Any
from sklearn.preprocessing import StandardScaler
import joblib

from backend.config import settings
from backend.preprocessing.feature_engineer import EngineeredFeatures, FeatureEngineer


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int, encoding_dim: int = 16, hidden_dims: List[int] = None):
        super().__init__()

        if hidden_dims is None:
            hidden_dims = [64, 32]

        encoder_layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1)
            ])
            prev_dim = hidden_dim
        encoder_layers.append(nn.Linear(prev_dim, encoding_dim))
        self.encoder = nn.Sequential(*encoder_layers)

        decoder_layers = []
        prev_dim = encoding_dim
        for hidden_dim in reversed(hidden_dims):
            decoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1)
            ])
            prev_dim = hidden_dim
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

    def encode(self, x):
        return self.encoder(x)

    def decode(self, z):
        return self.decoder(z)


class AutoencoderDetector:
    def __init__(
        self,
        input_dim: int = 33,
        encoding_dim: int = 16,
        hidden_dims: List[int] = None,
        learning_rate: float = 0.001,
        batch_size: int = 256,
        epochs: int = 50,
        device: str = None
    ):
        self.input_dim = input_dim
        self.encoding_dim = encoding_dim
        self.hidden_dims = hidden_dims or [64, 32]
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model: Optional[Autoencoder] = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = settings.AUTOENCODER_PATH
        self.threshold: Optional[float] = None

    def train(self, features: np.ndarray, validation_split: float = 0.1, save: bool = True) -> Dict[str, Any]:
        self.scaler.fit(features)
        scaled_features = self.scaler.transform(features)

        n_val = int(len(scaled_features) * validation_split)
        train_data = scaled_features[n_val:]
        val_data = scaled_features[:n_val]

        train_tensor = torch.FloatTensor(train_data).to(self.device)
        val_tensor = torch.FloatTensor(val_data).to(self.device)

        train_loader = DataLoader(TensorDataset(train_tensor), batch_size=self.batch_size, shuffle=True)

        self.model = Autoencoder(self.input_dim, self.encoding_dim, self.hidden_dims).to(self.device)
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate, weight_decay=1e-5)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        train_losses = []
        val_losses = []

        print(f"Training Autoencoder on {self.device}...")
        for epoch in range(self.epochs):
            self.model.train()
            epoch_loss = 0.0
            for batch in train_loader:
                optimizer.zero_grad()
                inputs = batch[0]
                outputs = self.model(inputs)
                loss = criterion(outputs, inputs)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            avg_train_loss = epoch_loss / len(train_loader)
            train_losses.append(avg_train_loss)

            self.model.eval()
            with torch.no_grad():
                val_outputs = self.model(val_tensor)
                val_loss = criterion(val_outputs, val_tensor).item()
                val_losses.append(val_loss)

            scheduler.step(val_loss)

            if (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{self.epochs}: Train Loss={avg_train_loss:.6f}, Val Loss={val_loss:.6f}")

        self.is_trained = True

        self.threshold = self._calculate_threshold(scaled_features)

        if save:
            self.save()

        return {
            "epochs": self.epochs,
            "final_train_loss": train_losses[-1],
            "final_val_loss": val_losses[-1],
            "threshold": self.threshold,
            "train_losses": train_losses,
            "val_losses": val_losses
        }

    def _calculate_threshold(self, features: np.ndarray, percentile: float = 95) -> float:
        self.model.eval()
        with torch.no_grad():
            tensor = torch.FloatTensor(features).to(self.device)
            reconstructed = self.model(tensor)
            errors = torch.mean((tensor - reconstructed) ** 2, dim=1).cpu().numpy()
        return float(np.percentile(errors, percentile))

    def predict(self, features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Call train() first or load a saved model.")

        scaled_features = self.scaler.transform(features)
        tensor = torch.FloatTensor(scaled_features).to(self.device)

        self.model.eval()
        with torch.no_grad():
            reconstructed = self.model(tensor)
            errors = torch.mean((tensor - reconstructed) ** 2, dim=1).cpu().numpy()

        anomaly_scores = self._convert_to_anomaly_score(errors)
        predictions = (anomaly_scores > 50).astype(int)

        return predictions, anomaly_scores

    def predict_single(self, feature_vector: np.ndarray) -> Tuple[int, float, np.ndarray]:
        pred, score = self.predict(feature_vector.reshape(1, -1))
        recon_error = self.get_reconstruction_error(feature_vector.reshape(1, -1))
        return int(pred[0]), float(score[0]), recon_error[0]

    def get_reconstruction_error(self, features: np.ndarray) -> np.ndarray:
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained.")

        scaled_features = self.scaler.transform(features)
        tensor = torch.FloatTensor(scaled_features).to(self.device)

        self.model.eval()
        with torch.no_grad():
            reconstructed = self.model(tensor)
            errors = torch.mean((tensor - reconstructed) ** 2, dim=1).cpu().numpy()

        return errors

    def get_reconstruction_per_feature(self, feature_vector: np.ndarray) -> np.ndarray:
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained.")

        scaled = self.scaler.transform(feature_vector.reshape(1, -1))
        tensor = torch.FloatTensor(scaled).to(self.device)

        self.model.eval()
        with torch.no_grad():
            reconstructed = self.model(tensor)
            per_feature_error = ((tensor - reconstructed) ** 2).cpu().numpy()[0]

        return per_feature_error

    def _convert_to_anomaly_score(self, errors: np.ndarray) -> np.ndarray:
        if self.threshold is None:
            return np.full_like(errors, 50.0)

        max_error = np.max(errors) if np.max(errors) > self.threshold else self.threshold * 2
        normalized = np.clip(errors / max_error, 0, 1)
        anomaly_scores = normalized * 100
        return anomaly_scores

    def save(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "input_dim": self.input_dim,
            "encoding_dim": self.encoding_dim,
            "hidden_dims": self.hidden_dims,
            "scaler": self.scaler,
            "threshold": self.threshold,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs
        }, self.model_path)

    def load(self) -> bool:
        if not os.path.exists(self.model_path):
            return False

        checkpoint = torch.load(self.model_path, map_location=self.device)
        self.input_dim = checkpoint["input_dim"]
        self.encoding_dim = checkpoint["encoding_dim"]
        self.hidden_dims = checkpoint["hidden_dims"]
        self.scaler = checkpoint["scaler"]
        self.threshold = checkpoint["threshold"]
        self.learning_rate = checkpoint["learning_rate"]
        self.batch_size = checkpoint["batch_size"]
        self.epochs = checkpoint["epochs"]

        self.model = Autoencoder(self.input_dim, self.encoding_dim, self.hidden_dims).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.is_trained = True
        return True


def train_autoencoder_from_historical(days: int = 30) -> AutoencoderDetector:
    from backend.simulation.aws_simulator import create_historical_data
    from backend.preprocessing.feature_engineer import FeatureEngineer

    print(f"Generating {days} days of historical data...")
    df = create_historical_data(days=days, interval_minutes=5)

    print("Engineering features...")
    engineer = FeatureEngineer()
    feature_df = engineer.engineer_batch(df)

    feature_cols = EngineeredFeatures.feature_names()
    X = feature_df[feature_cols].values

    print(f"Training Autoencoder on {len(X)} samples with {X.shape[1]} features...")
    detector = AutoencoderDetector(input_dim=X.shape[1], epochs=50)
    results = detector.train(X)

    print(f"Training complete. Threshold: {results['threshold']:.6f}")
    return detector