import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from backend.config import settings


class LSTMAutoencoder(nn.Module):
    def __init__(
        self,
        input_dim: int = 3,
        hidden_dim: int = 64,
        latent_dim: int = 16,
        num_layers: int = 2,
        sequence_length: int = 20,
        dropout: float = 0.1,
        bidirectional: bool = True
    ):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.num_layers = num_layers
        self.sequence_length = sequence_length
        self.dropout = dropout
        self.bidirectional = bidirectional
        self.num_directions = 2 if bidirectional else 1

        self.encoder_lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )

        encoder_output_dim = hidden_dim * self.num_directions
        self.latent_projection = nn.Linear(encoder_output_dim, latent_dim)
        self.latent_activation = nn.Tanh()

        self.decoder_input_projection = nn.Linear(latent_dim, encoder_output_dim)

        self.decoder_lstm = nn.LSTM(
            input_size=encoder_output_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )

        self.output_projection = nn.Linear(encoder_output_dim, input_dim)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, (h_n, c_n) = self.encoder_lstm(x)
        
        if self.bidirectional:
            h_n = h_n.view(self.num_layers, self.num_directions, x.size(0), self.hidden_dim)
            h_n = torch.cat([h_n[-1, 0], h_n[-1, 1]], dim=-1)
        else:
            h_n = h_n[-1]
        
        latent = self.latent_activation(self.latent_projection(h_n))
        return latent

    def decode(self, latent: torch.Tensor, seq_len: int) -> torch.Tensor:
        batch_size = latent.size(0)
        
        decoder_input = self.decoder_input_projection(latent)
        decoder_input = decoder_input.unsqueeze(1).repeat(1, seq_len, 1)
        
        lstm_out, _ = self.decoder_lstm(decoder_input)
        output = self.output_projection(lstm_out)
        return output

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        latent = self.encode(x)
        reconstruction = self.decode(latent, x.size(1))
        return reconstruction, latent


class LSTMAutoencoderModel:
    def __init__(
        self,
        input_dim: int = 3,
        hidden_dim: int = 64,
        latent_dim: int = 16,
        num_layers: int = 2,
        sequence_length: int = 20,
        learning_rate: float = 1e-3,
        dropout: float = 0.1,
        bidirectional: bool = True
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.num_layers = num_layers
        self.sequence_length = sequence_length
        self.learning_rate = learning_rate
        self.dropout = dropout
        self.bidirectional = bidirectional

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = LSTMAutoencoder(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            latent_dim=latent_dim,
            num_layers=num_layers,
            sequence_length=sequence_length,
            dropout=dropout,
            bidirectional=bidirectional
        ).to(self.device)

        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=10
        )

        self.is_fitted = False
        self.model_path = Path(settings.MODEL_DIR) / "lstm_autoencoder.pt"
        self.train_losses = []

    def create_sequences(self, data: np.ndarray) -> torch.Tensor:
        sequences = []
        for i in range(len(data) - self.sequence_length + 1):
            sequences.append(data[i:i + self.sequence_length])
        return torch.FloatTensor(np.array(sequences))

    def fit(
        self, 
        X: np.ndarray, 
        epochs: int = 50, 
        batch_size: int = 64, 
        validation_split: float = 0.2,
        verbose: bool = True
    ):
        sequences = self.create_sequences(X)
        
        n_val = int(len(sequences) * validation_split)
        train_seq = sequences[:-n_val] if n_val > 0 else sequences
        val_seq = sequences[-n_val:] if n_val > 0 else None

        train_dataset = torch.utils.data.TensorDataset(train_seq, train_seq)
        train_loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True
        )

        val_loader = None
        if val_seq is not None and len(val_seq) > 0:
            val_dataset = torch.utils.data.TensorDataset(val_seq, val_seq)
            val_loader = torch.utils.data.DataLoader(
                val_dataset, batch_size=batch_size, shuffle=False
            )

        self.model.train()
        self.train_losses = []

        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_x, _ in train_loader:
                batch_x = batch_x.to(self.device)
                
                self.optimizer.zero_grad()
                reconstructed, _ = self.model(batch_x)
                loss = self.criterion(reconstructed, batch_x)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                epoch_loss += loss.item()

            avg_train_loss = epoch_loss / len(train_loader)
            self.train_losses.append(avg_train_loss)

            val_loss = 0.0
            if val_loader:
                self.model.eval()
                with torch.no_grad():
                    for batch_x, _ in val_loader:
                        batch_x = batch_x.to(self.device)
                        reconstructed, _ = self.model(batch_x)
                        loss = self.criterion(reconstructed, batch_x)
                        val_loss += loss.item()
                avg_val_loss = val_loss / len(val_loader)
                self.scheduler.step(avg_val_loss)
                
                if verbose and (epoch + 1) % 10 == 0:
                    print(f"LSTM-AE Epoch {epoch+1}/{epochs} - Train: {avg_train_loss:.6f}, Val: {avg_val_loss:.6f}")
            else:
                if verbose and (epoch + 1) % 10 == 0:
                    print(f"LSTM-AE Epoch {epoch+1}/{epochs} - Train: {avg_train_loss:.6f}")

        self.is_fitted = True
        self.model.eval()

    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        sequences = self.create_sequences(X)
        dataset = torch.utils.data.TensorDataset(sequences, sequences)
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=64, shuffle=False
        )

        self.model.eval()
        errors = []
        with torch.no_grad():
            for batch_x, _ in loader:
                batch_x = batch_x.to(self.device)
                reconstructed, _ = self.model(batch_x)
                batch_errors = torch.mean((reconstructed - batch_x) ** 2, dim=(1, 2))
                errors.append(batch_errors.cpu().numpy())
        
        errors = np.concatenate(errors)
        
        padded_errors = np.zeros(len(X))
        padded_errors[:self.sequence_length - 1] = errors[0] if len(errors) > 0 else 0
        padded_errors[self.sequence_length - 1:] = errors
        
        return padded_errors

    def encode(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted.")
        
        sequences = self.create_sequences(X)
        dataset = torch.utils.data.TensorDataset(sequences)
        loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=False)

        self.model.eval()
        latents = []
        with torch.no_grad():
            for batch_x, in loader:
                batch_x = batch_x.to(self.device)
                _, latent = self.model(batch_x)
                latents.append(latent.cpu().numpy())
        
        return np.concatenate(latents)

    def save(self, path: Optional[Path] = None):
        path = path or self.model_path
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "input_dim": self.input_dim,
            "hidden_dim": self.hidden_dim,
            "latent_dim": self.latent_dim,
            "num_layers": self.num_layers,
            "sequence_length": self.sequence_length,
            "learning_rate": self.learning_rate,
            "dropout": self.dropout,
            "bidirectional": self.bidirectional,
            "train_losses": self.train_losses,
        }, path)

    def load(self, path: Optional[Path] = None):
        path = path or self.model_path
        checkpoint = torch.load(path, map_location=self.device)

        self.input_dim = checkpoint["input_dim"]
        self.hidden_dim = checkpoint["hidden_dim"]
        self.latent_dim = checkpoint["latent_dim"]
        self.num_layers = checkpoint["num_layers"]
        self.sequence_length = checkpoint["sequence_length"]
        self.learning_rate = checkpoint["learning_rate"]
        self.dropout = checkpoint["dropout"]
        self.bidirectional = checkpoint["bidirectional"]
        self.train_losses = checkpoint["train_losses"]

        self.model = LSTMAutoencoder(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            latent_dim=self.latent_dim,
            num_layers=self.num_layers,
            sequence_length=self.sequence_length,
            dropout=self.dropout,
            bidirectional=self.bidirectional
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.is_fitted = True
        self.model.eval()

    def get_params(self) -> Dict[str, Any]:
        return {
            "input_dim": self.input_dim,
            "hidden_dim": self.hidden_dim,
            "latent_dim": self.latent_dim,
            "num_layers": self.num_layers,
            "sequence_length": self.sequence_length,
            "learning_rate": self.learning_rate,
            "dropout": self.dropout,
            "bidirectional": self.bidirectional,
            "train_losses": self.train_losses[-10:] if self.train_losses else [],
        }

    def export_onnx(self, output_path: Path, input_shape: Tuple = (1, 20, 3)):
        self.model.eval()
        dummy_input = torch.randn(*input_shape).to(self.device)
        
        torch.onnx.export(
            self.model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=12,
            do_constant_folding=True,
            input_names=['input_sequence'],
            output_names=['reconstruction', 'latent'],
            dynamic_axes={
                'input_sequence': {0: 'batch_size', 1: 'sequence_length'},
                'reconstruction': {0: 'batch_size', 1: 'sequence_length'},
                'latent': {0: 'batch_size'}
            }
        )


def create_lstm_autoencoder(
    input_dim: int = 3,
    hidden_dim: int = 64,
    latent_dim: int = 16,
    sequence_length: int = 20
) -> LSTMAutoencoderModel:
    return LSTMAutoencoderModel(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        latent_dim=latent_dim,
        sequence_length=sequence_length
    )