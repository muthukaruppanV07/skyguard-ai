import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from backend.config import settings


class MultiHeadAttention(nn.Module):
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.w_o = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(d_model)
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size, seq_len, _ = x.shape
        
        q = self.w_q(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        k = self.w_k(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        v = self.w_v(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        
        scores = torch.matmul(q, k.transpose(-2, -1)) / np.sqrt(self.d_k)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = F.dropout(attn_weights, p=self.dropout.p, training=self.training)
        
        context = torch.matmul(attn_weights, v)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        
        output = self.w_o(context)
        output = self.layer_norm(output + x)
        
        return output, attn_weights


class TransformerEncoderLayer(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attention = MultiHeadAttention(d_model, num_heads, dropout)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout)
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        attn_out, _ = self.self_attention(x, mask)
        x = self.norm1(x + self.dropout(attn_out))
        
        ff_out = self.feed_forward(x)
        x = self.norm2(x + self.dropout(ff_out))
        
        return x


class TransformerAnomalyDetector(nn.Module):
    def __init__(
        self,
        input_dim: int = 30,
        d_model: int = 128,
        num_heads: int = 8,
        num_layers: int = 4,
        d_ff: int = 512,
        max_seq_len: int = 50,
        latent_dim: int = 32,
        dropout: float = 0.1,
        num_anomaly_types: int = 12
    ):
        super().__init__()
        self.input_dim = input_dim
        self.d_model = d_model
        self.max_seq_len = max_seq_len
        self.latent_dim = latent_dim
        
        self.input_projection = nn.Linear(input_dim, d_model)
        self.positional_encoding = self._create_positional_encoding(max_seq_len, d_model)
        
        self.encoder_layers = nn.ModuleList([
            TransformerEncoderLayer(d_model, 8, 512, 0.1) for _ in range(4)
        ])
        
        self.latent_projection = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(d_model // 2, latent_dim)
        )
        
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, d_model // 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(d_model // 2, d_model),
            nn.Linear(d_model, input_dim)
        )
        
        self.anomaly_classifier = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(latent_dim // 2, num_anomaly_types)
        )
        
        self.anomaly_score_head = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.GELU(),
            nn.Linear(latent_dim // 2, 1),
            nn.Sigmoid()
        )
        
        self.severity_head = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.GELU(),
            nn.Linear(latent_dim // 2, 5)
        )
        
        self.confidence_head = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.GELU(),
            nn.Linear(latent_dim // 2, 1),
            nn.Sigmoid()
        )
        
    def _create_positional_encoding(self, max_len: int, d_model: int) -> torch.Tensor:
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        return pe.unsqueeze(0)
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        batch_size, seq_len, _ = x.shape
        
        x = self.input_projection(x)
        x = x + self.positional_encoding[:, :x.size(1), :].to(x.device)
        
        for layer in self.encoder_layers:
            x = layer(x)
        
        pooled = x.mean(dim=1)
        latent = self.latent_projection(pooled)
        
        reconstruction = self.decoder(latent)
        
        anomaly_logits = self.anomaly_classifier(latent)
        anomaly_probs = F.softmax(anomaly_logits, dim=-1)
        
        anomaly_score = self.anomaly_score_head(latent).squeeze(-1)
        severity_logits = self.severity_head(latent)
        confidence = self.confidence_head(latent).squeeze(-1)
        
        return {
            'reconstruction': reconstruction,
            'latent': latent,
            'anomaly_logits': anomaly_logits,
            'anomaly_probs': anomaly_probs,
            'anomaly_score': anomaly_score,
            'severity_logits': severity_logits,
            'confidence': confidence
        }
    
    def get_attention_weights(self, x: torch.Tensor) -> List[torch.Tensor]:
        x = self.input_projection(x)
        x = x + self.positional_encoding[:, :x.size(1), :].to(x.device)
        
        attentions = []
        for layer in self.encoder_layers:
            _, attn = layer.self_attention(x)
            attentions.append(attn)
            x = layer(x)
        return attentions


class TransformerAnomalyModel:
    def __init__(
        self,
        input_dim: int = 30,
        d_model: int = 128,
        num_heads: int = 8,
        num_layers: int = 4,
        latent_dim: int = 32,
        sequence_length: int = 50,
        learning_rate: float = 1e-4,
        num_anomaly_types: int = 12
    ):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        self.model = TransformerAnomalyDetector(
            input_dim=input_dim,
            d_model=d_model,
            num_heads=num_heads,
            num_layers=num_layers,
            latent_dim=latent_dim,
            max_seq_len=sequence_length,
            num_anomaly_types=num_anomaly_types
        ).to(self.device)
        
        self.criterion_recon = nn.MSELoss()
        self.criterion_class = nn.CrossEntropyLoss()
        self.criterion_score = nn.BCELoss()
        self.criterion_severity = nn.CrossEntropyLoss()
        self.criterion_conf = nn.BCELoss()
        
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), 
            lr=learning_rate, 
            weight_decay=1e-4
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=100
        )
        
        self.sequence_length = 50
        self.is_fitted = False
        self.train_losses = []
        self.model_path = Path("models/transformer_anomaly.pt")
        
    def create_sequences(self, data: np.ndarray) -> torch.Tensor:
        sequences = []
        for i in range(len(data) - self.sequence_length + 1):
            sequences.append(data[i:i + self.sequence_length])
        return torch.FloatTensor(np.array(sequences))
    
    def fit(
        self, 
        X: np.ndarray, 
        y_anomaly: np.ndarray = None,
        y_severity: np.ndarray = None,
        epochs: int = 50, 
        batch_size: int = 32, 
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
            epoch_losses = {'total': 0, 'recon': 0, 'class': 0, 'score': 0, 'severity': 0}
            
            for batch_x, _ in train_loader:
                batch_x = batch_x.to(self.device)
                
                self.optimizer.zero_grad()
                outputs = self.model(batch_x)
                
                recon_loss = self.criterion_recon(outputs['reconstruction'], batch_x)
                
                target = torch.zeros(batch_x.size(0), dtype=torch.long).to(self.device)
                class_loss = self.criterion_class(outputs['anomaly_logits'], target)
                
                score_loss = self.criterion_score(outputs['anomaly_score'], torch.zeros_like(outputs['anomaly_score']))
                
                sev_target = torch.zeros(batch_x.size(0), dtype=torch.long).to(self.device)
                severity_loss = self.criterion_severity(outputs['severity_logits'], sev_target)
                
                total_loss = recon_loss + 0.5 * class_loss + 0.3 * score_loss + 0.2 * severity_loss
                
                total_loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                
                epoch_losses['total'] += total_loss.item()
                epoch_losses['recon'] += recon_loss.item()
                epoch_losses['class'] += class_loss.item()
                epoch_losses['score'] += score_loss.item()
                epoch_losses['severity'] += severity_loss.item()
            
            avg_losses = {k: v / len(train_loader) for k, v in epoch_losses.items()}
            self.train_losses.append(avg_losses)
            
            if verbose and (epoch + 1) % 10 == 0:
                print(f"Transformer Epoch {epoch+1}/{epochs} - "
                      f"Total: {avg_losses['total']:.4f}, "
                      f"Recon: {avg_losses['recon']:.4f}, "
                      f"Class: {avg_losses['class']:.4f}")
        
        self.is_fitted = True
        self.model.eval()
    
    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        sequences = self.create_sequences(X)
        dataset = torch.utils.data.TensorDataset(sequences)
        loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=False)
        
        self.model.eval()
        results = {
            'reconstruction': [],
            'latent': [],
            'anomaly_probs': [],
            'anomaly_score': [],
            'severity': [],
            'confidence': []
        }
        
        with torch.no_grad():
            for batch_x, in loader:
                batch_x = batch_x.to(self.device)
                outputs = self.model(batch_x)
                
                results['reconstruction'].append(outputs['reconstruction'].cpu().numpy())
                results['latent'].append(outputs['latent'].cpu().numpy())
                results['anomaly_probs'].append(outputs['anomaly_probs'].cpu().numpy())
                results['anomaly_score'].append(outputs['anomaly_score'].cpu().numpy())
                results['severity'].append(F.softmax(outputs['severity_logits'], dim=-1).cpu().numpy())
                results['confidence'].append(outputs['confidence'].cpu().numpy())
        
        return {k: np.concatenate(v) for k, v in results.items()}
    
    def get_attention_maps(self, X: np.ndarray) -> List[np.ndarray]:
        sequences = self.create_sequences(X[:1])
        x = sequences.to(self.device)
        self.model.eval()
        with torch.no_grad():
            attentions = self.model.get_attention_weights(x)
        return [a.cpu().numpy() for a in attentions]
    
    def save(self, path: str = None):
        path = path or self.model_path
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'train_losses': self.train_losses,
        }, path)
    
    def load(self, path: str = None):
        path = path or self.model_path
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.train_losses = checkpoint['train_losses']
        self.is_fitted = True
        self.model.eval()
    
    def export_onnx(self, output_path: Path, input_shape: Tuple = (1, 50, 30)):
        self.model.eval()
        dummy_input = torch.randn(*input_shape).to(self.device)
        
        torch.onnx.export(
            self.model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=['input_sequence'],
            output_names=['reconstruction', 'latent', 'anomaly_probs', 'anomaly_score', 'severity', 'confidence'],
            dynamic_axes={
                'input_sequence': {0: 'batch_size', 1: 'sequence_length'},
                'reconstruction': {0: 'batch_size', 1: 'sequence_length'},
                'latent': {0: 'batch_size'},
                'anomaly_probs': {0: 'batch_size'},
                'anomaly_score': {0: 'batch_size'},
                'severity': {0: 'batch_size'},
                'confidence': {0: 'batch_size'}
            }
        )


def create_transformer_anomaly(
    input_dim: int = 30,
    d_model: int = 128,
    num_layers: int = 4,
    latent_dim: int = 32,
    sequence_length: int = 50
) -> "TransformerAnomalyModel":
    return TransformerAnomalyModel(
        input_dim=input_dim,
        d_model=d_model,
        num_layers=4,
        latent_dim=latent_dim,
        sequence_length=sequence_length
    )