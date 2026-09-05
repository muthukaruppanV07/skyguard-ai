import mlflow
import mlflow.sklearn
import mlflow.pytorch
import mlflow.onnx
from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType
from mlflow.models.signature import ModelSignature
from mlflow.types.schema import Schema, TensorSpec
import numpy as np
import pandas as pd
import torch
import joblib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from backend.config import settings
from backend.anomaly.isolation_forest import IsolationForestModel
from backend.anomaly.autoencoder import AutoencoderModel
from backend.anomaly.lstm_autoencoder import LSTMAutoencoderModel
from backend.anomaly.transformer_anomaly import TransformerAnomalyModel
from backend.preprocessing.scaler import FeatureScaler
import json
import tempfile
import shutil


class ModelStage(Enum):
    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


class ModelType(Enum):
    ISOLATION_FOREST = "isolation_forest"
    AUTOENCODER = "autoencoder"
    LSTM_AUTOENCODER = "lstm_autoencoder"
    TRANSFORMER = "transformer"
    ENSEMBLE = "ensemble"


@dataclass
class ModelVersion:
    name: str
    version: str
    stage: ModelStage
    model_type: ModelType
    run_id: str
    metrics: Dict[str, float]
    params: Dict[str, Any]
    created_at: datetime
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    signature: Optional[str] = None
    input_example: Optional[np.ndarray] = None


class MLflowModelRegistry:
    def __init__(
        self,
        tracking_uri: str = "sqlite:///mlflow.db",
        registry_uri: str = None,
        experiment_name: str = "skyguard-anomaly-detection"
    ):
        self.tracking_uri = tracking_uri
        self.registry_uri = registry_uri or tracking_uri
        self.experiment_name = experiment_name
        
        mlflow.set_tracking_uri(self.tracking_uri)
        if self.registry_uri:
            mlflow.set_registry_uri(self.registry_uri)
        
        self.client = MlflowClient(tracking_uri=self.tracking_uri, registry_uri=self.registry_uri)
        
        self.experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if not self.experiment:
            self.experiment_id = mlflow.create_experiment(self.experiment_name)
        else:
            self.experiment_id = self.experiment.experiment_id
        
        mlflow.set_experiment(self.experiment_name)
    
    def log_model_run(
        self,
        model_name: str,
        model_type: ModelType,
        model_obj: Any,
        scaler: FeatureScaler,
        X_train: np.ndarray,
        y_train: np.ndarray = None,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None,
        metrics: Dict[str, float] = None,
        params: Dict[str, Any] = None,
        description: str = "",
        tags: Dict[str, str] = None,
        input_example: np.ndarray = None,
        signature: ModelSignature = None
    ) -> str:
        with mlflow.start_run(experiment_id=self.experiment_id) as run:
            run_id = run.info.run_id
            
            if params:
                mlflow.log_params(params)
            
            if metrics:
                mlflow.log_metrics(metrics)
            
            if tags:
                mlflow.set_tags(tags)
            
            mlflow.set_tag("model_type", model_type.value)
            mlflow.set_tag("model_name", model_name)
            
            if input_example is not None:
                mlflow.log_input(mlflow.data.from_numpy(input_example), context="training")
            
            if model_type == ModelType.ISOLATION_FOREST:
                mlflow.sklearn.log_model(
                    model_obj.model,
                    artifact_path="model",
                    registered_model_name=model_name,
                    signature=signature,
                    input_example=input_example
                )
            elif model_type in [ModelType.AUTOENCODER, ModelType.LSTM_AUTOENCODER, ModelType.TRANSFORMER]:
                mlflow.pytorch.log_model(
                    model_obj.model,
                    artifact_path="model",
                    registered_model_name=model_name,
                    signature=signature,
                    input_example=input_example
                )
            elif model_type == ModelType.ENSEMBLE:
                mlflow.pyfunc.log_model(
                    artifact_path="model",
                    python_model=model_obj,
                    registered_model_name=model_name,
                    signature=signature,
                    input_example=input_example
                )
            
            mlflow.sklearn.log_model(
                scaler.scaler,
                artifact_path="scaler"
            )
            
            if hasattr(model_obj, 'train_losses') and model_obj.train_losses:
                for i, loss in enumerate(model_obj.train_losses):
                    mlflow.log_metric("train_loss", loss, step=i)
            
            return run_id
    
    def register_model(
        self,
        run_id: str,
        model_name: str,
        description: str = "",
        await_registration: bool = True
    ) -> str:
        model_uri = f"runs:/{run_id}/model"
        
        result = mlflow.register_model(
            model_uri=model_uri,
            name=model_name,
            await_registration_for=300 if await_registration else None
        )
        
        if description:
            self.client.update_model_version(
                name=model_name,
                version=result.version,
                description=description
            )
        
        return result.version
    
    def transition_stage(
        self,
        model_name: str,
        version: str,
        stage: ModelStage,
        archive_existing: bool = True
    ) -> bool:
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage.value,
                archive_existing_versions=archive_existing
            )
            return True
        except Exception as e:
            print(f"Failed to transition model stage: {e}")
            return False
    
    def get_model_version(self, model_name: str, version: str) -> ModelVersion:
        mv = self.client.get_model_version(model_name, version)
        run = self.client.get_run(mv.run_id)
        
        return ModelVersion(
            name=mv.name,
            version=mv.version,
            stage=ModelStage(mv.current_stage),
            model_type=ModelType(mv.tags.get("model_type", "unknown")),
            run_id=mv.run_id,
            metrics=run.data.metrics,
            params=run.data.params,
            created_at=datetime.fromtimestamp(mv.creation_timestamp / 1000),
            description=mv.description or "",
            tags=mv.tags
        )
    
    def get_latest_version(self, model_name: str, stage: ModelStage = ModelStage.PRODUCTION) -> Optional[ModelVersion]:
        versions = self.client.get_latest_versions(model_name, stages=[stage.value])
        if not versions:
            return None
        return self.get_model_version(model_name, versions[0].version)
    
    def get_all_versions(self, model_name: str) -> List[ModelVersion]:
        versions = self.client.search_model_versions(f"name='{model_name}'")
        return [self.get_model_version(model_name, v.version) for v in versions]
    
    def compare_versions(self, model_name: str, version1: str, version2: str) -> Dict[str, Any]:
        v1 = self.get_model_version(model_name, version1)
        v2 = self.get_model_version(model_name, version2)
        
        comparison = {
            "version1": {"version": v1.version, "metrics": v1.metrics, "params": v1.params},
            "version2": {"version": v2.version, "metrics": v2.metrics, "params": v2.params},
            "metric_diff": {}
        }
        
        for metric in set(v1.metrics.keys()) | set(v2.metrics.keys()):
            v1_val = v1.metrics.get(metric, 0)
            v2_val = v2.metrics.get(metric, 0)
            comparison["metric_diff"][metric] = {
                "v1": v1_val,
                "v2": v2_val,
                "diff": v2_val - v1_val,
                "pct_change": ((v2_val - v1_val) / v1_val * 100) if v1_val != 0 else float('inf')
            }
        
        return comparison
    
    def promote_to_production(self, model_name: str, version: str = None) -> bool:
        if version is None:
            latest = self.get_latest_version(model_name, ModelStage.STAGING)
            if not latest:
                return False
            version = latest.version
        
        return self.transition_stage(model_name, version, ModelStage.PRODUCTION)
    
    def archive_model(self, model_name: str, version: str) -> bool:
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=ModelStage.ARCHIVED.value
            )
            return True
        except Exception as e:
            print(f"Failed to archive model: {e}")
            return False
    
    def get_model_metrics_history(self, model_name: str, version: str = None) -> pd.DataFrame:
        if version:
            runs = self.client.search_runs(
                experiment_ids=[self.experiment_id],
                filter_string=f"tags.model_name='{model_name}' AND tags.mlflow.runName='{version}'",
                run_view_type=ViewType.ACTIVE_ONLY
            )
        else:
            runs = self.client.search_runs(
                experiment_ids=[self.experiment_id],
                filter_string=f"tags.model_name='{model_name}'",
                run_view_type=ViewType.ACTIVE_ONLY
            )
        
        records = []
        for run in runs:
            records.append({
                "run_id": run.info.run_id,
                "model_name": run.data.tags.get("model_name"),
                "model_type": run.data.tags.get("model_type"),
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
                **run.data.metrics
            })
        
        return pd.DataFrame(records)
    
    def log_evaluation_metrics(
        self,
        run_id: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_scores: np.ndarray = None,
        prefix: str = "eval"
    ):
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
        
        metrics = {
            f"{prefix}_accuracy": accuracy_score(y_true, y_pred),
            f"{prefix}_precision": precision_score(y_true, y_pred, average='weighted', zero_division=0),
            f"{prefix}_recall": recall_score(y_true, y_pred, average='weighted', zero_division=0),
            f"{prefix}_f1": f1_score(y_true, y_pred, average='weighted', zero_division=0),
        }
        
        if y_scores is not None and len(np.unique(y_true)) == 2:
            metrics[f"{prefix}_roc_auc"] = roc_auc_score(y_true, y_scores)
        
        with mlflow.start_run(run_id=run_id):
            mlflow.log_metrics(metrics)
        
        return metrics
    
    def create_model_signature(self, X: np.ndarray, y: np.ndarray = None) -> ModelSignature:
        from mlflow.models.signature import infer_signature
        return infer_signature(X, y)
    
    def export_model_for_serving(
        self,
        model_name: str,
        version: str,
        export_path: str,
        format: str = "onnx"
    ) -> bool:
        mv = self.get_model_version(model_name, version)
        
        if format == "onnx":
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    local_path = mlflow.artifacts.download_artifacts(
                        artifact_uri=f"runs:/{mv.run_id}/model",
                        dst_path=tmpdir
                    )
                    
                    if mv.model_type == ModelType.ISOLATION_FOREST:
                        model = mlflow.sklearn.load_model(local_path)
                        import onnxmltools
                        onnx_model = onnxmltools.convert_sklearn(model)
                        onnxmltools.utils.save_model(onnx_model, Path(export_path) / f"{model_name}.onnx")
                    else:
                        model = mlflow.pytorch.load_model(local_path)
                        dummy_input = torch.randn(1, 30)
                        torch.onnx.export(
                            model, dummy_input,
                            Path(export_path) / f"{model_name}.onnx",
                            export_params=True, opset_version=12
                        )
            except Exception as e:
                print(f"ONNX export failed: {e}")
                return False
        
        return True


class ModelDeploymentManager:
    def __init__(self, registry: MLflowModelRegistry):
        self.registry = registry
        self.deployed_models: Dict[str, Dict[str, Any]] = {}
    
    def deploy_model(
        self,
        model_name: str,
        version: str = None,
        target: str = "local",
        config: Dict = None
    ) -> bool:
        if version is None:
            mv = self.registry.get_latest_version(model_name, ModelStage.PRODUCTION)
            if not mv:
                return False
            version = mv.version
        
        mv = self.registry.get_model_version(model_name, version)
        
        if target == "local":
            return self._deploy_local(mv)
        elif target == "docker":
            return self._deploy_docker(mv, config)
        elif target == "kubernetes":
            return self._deploy_kubernetes(mv, config)
        
        return False
    
    def _deploy_local(self, model_version: ModelVersion) -> bool:
        self.deployed_models[model_version.name] = {
            "version": model_version.version,
            "stage": model_version.stage,
            "run_id": model_version.run_id,
            "deployed_at": datetime.utcnow(),
            "target": "local",
            "model_path": f"models:/{model_version.name}/{model_version.version}"
        }
        return True
    
    def _deploy_docker(self, model_version: ModelVersion, config: Dict) -> bool:
        pass
    
    def _deploy_kubernetes(self, model_version: ModelVersion, config: Dict) -> bool:
        pass
    
    def get_deployed_models(self) -> Dict[str, Dict]:
        return self.deployed_models
    
    def rollback(self, model_name: str, previous_version: str) -> bool:
        mv = self.registry.get_model_version(model_name, previous_version)
        if not mv:
            return False
        
        return self.registry.transition_stage(model_name, previous_version, ModelStage.PRODUCTION)


class ExperimentTracker:
    def __init__(self, registry: MLflowModelRegistry):
        self.registry = registry
    
    def log_hyperparameter_tuning(
        self,
        study_name: str,
        trial_params: Dict,
        trial_metrics: Dict,
        trial_number: int
    ):
        with mlflow.start_run(experiment_id=self.registry.experiment_id, run_name=f"{study_name}_trial_{trial_number}"):
            mlflow.log_params(trial_params)
            mlflow.log_metrics(trial_metrics)
            mlflow.set_tag("study_name", study_name)
            mlflow.set_tag("trial_number", trial_number)
    
    def log_cross_validation(
        self,
        model_name: str,
        cv_results: Dict,
        fold_metrics: List[Dict],
        params: Dict
    ):
        with mlflow.start_run(experiment_id=self.registry.experiment_id, run_name=f"{model_name}_cv"):
            mlflow.log_params(params)
            
            for i, fold in enumerate(fold_metrics):
                for metric, value in fold.items():
                    mlflow.log_metric(f"fold_{i}_{metric}", value)
            
            for metric in cv_results:
                if metric.endswith("_mean") or metric.endswith("_std"):
                    mlflow.log_metric(metric, cv_results[metric])
            
            mlflow.log_params(params)
            mlflow.set_tag("model_name", model_name)
            mlflow.set_tag("evaluation_type", "cross_validation")
    
    def log_model_comparison(
        self,
        models: List[Tuple[str, Dict[str, float]]],
        comparison_name: str
    ):
        with mlflow.start_run(experiment_id=self.registry.experiment_id, run_name=f"comparison_{comparison_name}"):
            for model_name, metrics in models:
                for metric, value in metrics.items():
                    mlflow.log_metric(f"{model_name}_{metric}", value)
            
            mlflow.set_tag("comparison_name", comparison_name)
            mlflow.set_tag("type", "model_comparison")


def create_mlflow_registry(
    tracking_uri: str = "sqlite:///mlflow.db",
    experiment_name: str = "skyguard-anomaly-detection"
) -> MLflowModelRegistry:
    return MLflowModelRegistry(tracking_uri, experiment_name=experiment_name)


def create_model_deployment_manager(registry: MLflowModelRegistry) -> ModelDeploymentManager:
    return ModelDeploymentManager(registry)


def create_experiment_tracker(registry: MLflowModelRegistry) -> ExperimentTracker:
    return ExperimentTracker(registry)


def setup_mlflow_for_skyguard():
    registry = create_mlflow_registry()
    deployment = create_model_deployment_manager(registry)
    tracker = create_experiment_tracker(registry)
    
    return {
        "registry": registry,
        "deployment": deployment,
        "tracker": tracker
    }