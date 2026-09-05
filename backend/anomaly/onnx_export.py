import torch
import numpy as np
import onnx
import onnxruntime as ort
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import joblib
from pathlib import Path
from typing import Tuple, Optional
from backend.config import settings
from backend.anomaly.isolation_forest import IsolationForestModel
from backend.anomaly.autoencoder import AutoencoderModel
from backend.preprocessing.scaler import FeatureScaler


class ONNXExporter:
    def __init__(self, model_dir: Path = None):
        self.model_dir = model_dir or Path(settings.MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def export_isolation_forest(self, if_model: IsolationForestModel, scaler: FeatureScaler, 
                                 input_dim: int, output_path: Path = None) -> Path:
        output_path = output_path or self.model_dir / "isolation_forest.onnx"
        
        initial_type = [('float_input', FloatTensorType([None, input_dim]))]
        
        onnx_model = convert_sklearn(
            if_model.model,
            initial_types=initial_type,
            target_opset=12
        )
        
        with open(output_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        
        print(f"Isolation Forest ONNX exported to: {output_path}")
        return output_path

    def export_autoencoder(self, ae_model: AutoencoderModel, input_dim: int, 
                           output_path: Path = None) -> Path:
        output_path = output_path or self.model_dir / "autoencoder.onnx"
        
        ae_model.model.eval()
        dummy_input = torch.randn(1, input_dim)
        
        torch.onnx.export(
            ae_model.model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=12,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['reconstruction', 'latent'],
            dynamic_axes={
                'input': {0: 'batch_size'},
                'reconstruction': {0: 'batch_size'},
                'latent': {0: 'batch_size'}
            }
        )
        
        print(f"Autoencoder ONNX exported to: {output_path}")
        return output_path

    def export_scaler(self, scaler: FeatureScaler, input_dim: int, 
                      output_path: Path = None) -> Path:
        output_path = output_path or self.model_dir / "scaler.onnx"
        
        initial_type = [('float_input', FloatTensorType([None, input_dim]))]
        
        onnx_model = convert_sklearn(
            scaler.scaler,
            initial_types=initial_type,
            target_opset=12
        )
        
        with open(output_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        
        print(f"Scaler ONNX exported to: {output_path}")
        return output_path

    def export_pipeline(self, if_model: IsolationForestModel, ae_model: AutoencoderModel,
                        scaler: FeatureScaler, input_dim: int) -> dict:
        paths = {}
        paths['isolation_forest'] = self.export_isolation_forest(if_model, scaler, input_dim)
        paths['autoencoder'] = self.export_autoencoder(ae_model, input_dim)
        paths['scaler'] = self.export_scaler(scaler, input_dim)
        
        return paths

    def validate_onnx(self, model_path: Path, test_input: np.ndarray) -> bool:
        try:
            session = ort.InferenceSession(str(model_path))
            inputs = {session.get_inputs()[0].name: test_input.astype(np.float32)}
            outputs = session.run(None, inputs)
            print(f"ONNX validation passed for {model_path.name}")
            print(f"  Input shape: {test_input.shape}")
            print(f"  Output shapes: {[o.shape for o in outputs]}")
            return True
        except Exception as e:
            print(f"ONNX validation failed for {model_path}: {e}")
            return False


def export_all_models():
    from backend.anomaly.isolation_forest import IsolationForestModel
    from backend.anomaly.autoencoder import AutoencoderModel
    from backend.preprocessing.scaler import FeatureScaler
    
    print("Loading models...")
    if_model = IsolationForestModel()
    if_model.load()
    
    ae_model = AutoencoderModel(input_dim=30)
    ae_model.load()
    
    scaler = FeatureScaler()
    scaler.load()
    
    print("Exporting to ONNX...")
    exporter = ONNXExporter()
    paths = exporter.export_pipeline(if_model, ae_model, scaler, input_dim=30)
    
    test_input = np.random.randn(1, 30).astype(np.float32)
    for name, path in paths.items():
        exporter.validate_onnx(path, test_input)
    
    return paths


if __name__ == "__main__":
    export_all_models()