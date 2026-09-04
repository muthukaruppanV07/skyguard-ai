import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.config import settings, AUTOENCODER_PATH


class Autoencoder(nn.Module):
    def __init__(
        self,
        input_dim: int = settings.AE_INPUT_DIM,
        encoding_dim: int = settings.AE_ENCODING_DIM,
        hidden_dims: List[int] = None,
        dropout: float = settings.AE_DROPOUT,
    ):
        super().__init__()
        hidden_dims = hidden_dims or settings.AE_HIDDEN_DIMS
        
        encoder_layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
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
                nn.Dropout(dropout),
            ])
            prev_dim = hidden_dim
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded, encoded


class AutoencoderModel:
    def __init__(
        self,
        input_dim: int = settings.AE_INPUT_DIM,
        encoding_dim: int = settings.AE_ENCODING_DIM,
        hidden_dims: List[int] = None,
        learning_rate: float = settings.AE_LEARNING_RATE,
        dropout: float = settings.AE_DROPOUT,
    ):
        self.input_dim = input_dim
        self.encoding_dim = encoding_dim
        self.hidden_dims = hidden_dims or settings.AE_HIDDEN_DIMS
        self.learning_rate = learning_rate
        self.dropout = dropout
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = Autoencoder(input_dim, encoding_dim, self.hidden_dims, dropout).to(self.device)
        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        
        self.is_fitted = False
        self.model_path = AUTOENCODER_PATH
        self.train_losses = []

    def fit(self, X: np.ndarray, epochs: int = None, batch_size: int = None, verbose: bool = True):
        epochs = epochs or settings.AE_EPOCHS
        batch_size = batch_size or settings.AE_BATCH_SIZE
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        dataset = torch.utils.data.TensorDataset(X_tensor, X_tensor)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        self.model.train()
        self.train_losses = []
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_x, _ in loader:
                self.optimizer.zero_grad()
                reconstructed, _ = self.model(batch_x)
                loss = self.criterion(reconstructed, batch_x)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item()
            
            avg_loss = epoch_loss / len(loader)
            self.train_losses.append(avg_loss)
            
            if verbose and (epoch + 1) % 10 == 0:
                print(f"AE Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}")
        
        self.is_fitted = True
        self.model.eval()

    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed, _ = self.model(X_tensor)
            errors = torch.mean((reconstructed - X_tensor) ** 2, dim=1).cpu().numpy()
        
        min_err = errors.min()
        max_err = errors.max()
        if max_err > min_err:
            normalized = (errors - min_err) / (max_err - min_err)
        else:
            normalized = np.zeros_like(errors)
        
        return normalized * 100

    def encode(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted.")
        
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            _, encoded = self.model(X_tensor)
            return encoded.cpu().numpy()

    def save(self, path: Optional[Path] = None):
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "input_dim": self.input_dim,
            "encoding_dim": self.encoding_dim,
            "hidden_dims": self.hidden_dims,
            "learning_rate": self.learning_rate,
            "dropout": self.dropout,
            "train_losses": self.train_losses,
        }, path or self.model_path)

    def load(self, path: Optional[Path] = None):
        checkpoint = torch.load(path or self.model_path, map_location=self.device)
        
        self.input_dim = checkpoint["input_dim"]
        self.encoding_dim = checkpoint["encoding_dim"]
        self.hidden_dims = checkpoint["hidden_dims"]
        self.learning_rate = checkpoint["learning_rate"]
        self.dropout = checkpoint["dropout"]
        self.train_losses = checkpoint["train_losses"]
        
        self.model = Autoencoder(
            self.input_dim, self.encoding_dim, self.hidden_dims, self.dropout
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.is_fitted = True
        self.model.eval()

    def get_params(self) -> Dict[str, Any]:
        return {
            "input_dim": self.input_dim,
            "encoding_dim": self.encoding_dim,
            "hidden_dims": self.hidden_dims,
            "learning_rate": self.learning_rate,
            "dropout": self.dropout,
            "train_losses": self.train_losses[-10:] if self.train_losses else [],
        }


def create_autoencoder(
    input_dim: int = settings.AE_INPUT_DIM,
    encoding_dim: int = settings.AE_ENCODING_DIM,
) -> AutoencoderModel:
    return AutoencoderModel(input_dim=input_dim, encoding_dim=encoding_dim)