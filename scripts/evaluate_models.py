import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from backend.config import settings
from backend.database.session import init_db, AsyncSessionLocal
from backend.models import Station, Reading
from backend.simulation.aws_simulator import AWSSimulator
from backend.simulation.anomaly_injector import AnomalyInjector
from backend.preprocessing import FeatureEngineer, FeatureScaler
from backend.anomaly import (
    IsolationForestModel, AutoencoderModel, RuleEngine,
    TemporalAnalyzer, MultivariateAnalyzer, SpatialAnalyzer,
    AnomalyFusion, RootCauseClassifier
)
from backend.database.repositories import ModelRunRepository
from backend.models.model_run import ModelType


class ModelEvaluator:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.scaler = FeatureScaler()
        self.if_model = IsolationForestModel()
        self.ae_model = AutoencoderModel()
        self.rule_engine = RuleEngine()
        self.temporal = TemporalAnalyzer()
        self.multivariate = MultivariateAnalyzer()
        self.spatial = SpatialAnalyzer()
        self.fusion = AnomalyFusion()
        self.root_cause = RootCauseClassifier()
        
        self.results = {
            'rule_only': [],
            'if_only': [],
            'ae_only': [],
            'hybrid': [],
            'ground_truth': [],
        }

    async def load_models(self):
        self.scaler.load()
        self.if_model.load()
        self.ae_model.load()
        print("Models loaded successfully")

    async def generate_test_data(self, db, days: int = 7) -> pd.DataFrame:
        print(f"Generating {days} days of test data with injected anomalies...")
        
        simulator = AWSSimulator(db)
        await simulator.reset()
        
        injector = AnomalyInjector(db)
        
        injection_schedule = [
            (0, "AWS001", "TEMPERATURE_SPIKE", {"magnitude": 25}),
            (100, "AWS002", "TEMPERATURE_DRIFT", {"rate": 1.5, "duration_minutes": 60}),
            (200, "AWS003", "FROZEN_SENSOR", {"sensor": "humidity", "duration_minutes": 30}),
            (300, "AWS004", "COMMUNICATION_FAILURE", {"duration_minutes": 15}),
            (400, "AWS005", "MULTIVARIATE_INCONSISTENCY", {}),
            (500, "AWS006", "PRESSURE_SPIKE", {"magnitude": 35}),
            (600, "AWS007", "HUMIDITY_SPIKE", {"magnitude": 40, "direction": -1}),
            (700, "AWS008", "SENSOR_DEGRADATION", {"factor": 4.0}),
        ]
        
        start_time = datetime.utcnow().replace(second=0, microsecond=0) - timedelta(days=days)
        current_time = start_time
        end_time = datetime.utcnow()
        
        all_readings = []
        injection_idx = 0
        
        while current_time <= end_time:
            if injection_idx < len(injection_schedule):
                step, station_id, fault_type, params = injection_schedule[injection_idx]
                if len(all_readings) >= step:
                    await injector.inject(station_id, fault_type, params)
                    injection_idx += 1
            
            readings = await simulator.generate_all_readings(current_time)
            for r in readings:
                all_readings.append({
                    'station_id': r.station_id,
                    'timestamp': r.timestamp,
                    'temperature': r.temperature,
                    'pressure': r.pressure,
                    'humidity': r.humidity,
                })
            
            for r in readings:
                db.add(r)
            await db.commit()
            
            current_time += timedelta(minutes=1)
        
        df = pd.DataFrame(all_readings)
        ground_truth = injector.get_ground_truth()
        
        print(f"Generated {len(df)} readings with {len(ground_truth)} injected anomalies")
        return df, ground_truth

    def prepare_features(self, df: pd.DataFrame):
        all_features = []
        all_indices = []
        
        for station_id in df['station_id'].unique():
            station_df = df[df['station_id'] == station_id].sort_values('timestamp')
            readings = station_df.to_dict('records')
            
            features_df = self.feature_engineer.engineer_features(
                readings=readings,
                station_id=station_id,
            )
            model_features = self.feature_engineer.get_model_features(features_df)
            all_features.append(model_features)
            all_indices.extend(station_df.index.tolist())
        
        X = np.vstack(all_features)
        X_scaled = self.scaler.transform(X)
        return X_scaled, np.array(all_indices)

    def run_detection(self, X_scaled, df, indices):
        predictions = {}
        
        for i, idx in enumerate(indices):
            row = df.iloc[idx]
            station_id = row['station_id']
            
            history = df[(df['station_id'] == station_id) & (df.index < idx)].tail(120).to_dict('records')
            current = row.to_dict()
            
            rule_result = self.rule_engine.compute_score(current, history)
            
            if_score = self.if_model.predict_score(X_scaled[i:i+1])[0] if self.if_model.is_fitted else 0
            ae_score = self.ae_model.reconstruction_error(X_scaled[i:i+1])[0] if self.ae_model.is_fitted else 0
            
            temporal_result = self.temporal.analyze(current, history)
            multivariate_result = self.multivariate.analyze(current, history)
            spatial_result = {'spatial_score': 0}
            
            fusion_result = self.fusion.fuse(
                rule_score=rule_result['rule_score'],
                if_score=if_score,
                ae_score=ae_score,
                temporal_score=temporal_result['temporal_score'],
                multivariate_score=multivariate_result['multivariate_score'],
                spatial_score=spatial_result['spatial_score'],
            )
            
            predictions[idx] = {
                'rule_score': rule_result['rule_score'],
                'if_score': if_score,
                'ae_score': ae_score,
                'temporal_score': temporal_result['temporal_score'],
                'multivariate_score': multivariate_result['multivariate_score'],
                'spatial_score': spatial_result['spatial_score'],
                'hybrid_score': fusion_result['anomaly_score'],
                'severity': fusion_result['severity'],
                'confidence': fusion_result['confidence'],
            }
        
        return predictions

    def evaluate(self, predictions, ground_truth, df):
        gt_by_idx = {}
        for gt in ground_truth:
            for idx, row in df.iterrows():
                if row['station_id'] == gt['station_id'] and abs((row['timestamp'] - gt['timestamp']).total_seconds()) < 60:
                    gt_by_idx[idx] = gt
                    break
        
        metrics = {'rule_only': {}, 'if_only': {}, 'ae_only': {}, 'hybrid': {}}
        
        for method in ['rule_score', 'if_score', 'ae_score', 'hybrid_score']:
            method_key = method.replace('_score', '')
            if method_key == 'hybrid':
                method_key = 'hybrid'
            
            y_true = []
            y_pred = []
            
            for idx, pred in predictions.items():
                is_anomaly = idx in gt_by_idx
                y_true.append(1 if is_anomaly else 0)
                y_pred.append(1 if pred[method] > 50 else 0)
            
            y_true = np.array(y_true)
            y_pred = np.array(y_pred)
            
            tp = np.sum((y_true == 1) & (y_pred == 1))
            fp = np.sum((y_true == 0) & (y_pred == 1))
            fn = np.sum((y_true == 1) & (y_pred == 0))
            tn = np.sum((y_true == 0) & (y_pred == 0))
            
            accuracy = (tp + tn) / len(y_true) if len(y_true) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
            
            metrics[method_key] = {
                'accuracy': float(accuracy),
                'precision': float(precision),
                'recall': float(recall),
                'f1': float(f1),
                'fpr': float(fpr),
                'fnr': float(fnr),
                'tp': int(tp),
                'fp': int(fp),
                'fn': int(fn),
                'tn': int(tn),
            }
        
        return metrics

    def plot_results(self, metrics, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        
        methods = ['rule_only', 'if_only', 'ae_only', 'hybrid']
        metric_names = ['accuracy', 'precision', 'recall', 'f1', 'fpr', 'fnr']
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()
        
        for i, metric in enumerate(metric_names):
            values = [metrics[m][metric] for m in methods]
            bars = axes[i].bar(methods, values, color=['#3b82f6', '#ef4444', '#8b5cf6', '#22c55e'])
            axes[i].set_title(metric.upper())
            axes[i].set_ylim(0, 1.1)
            for bar, val in zip(bars, values):
                axes[i].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                           f'{val:.3f}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(output_dir / 'metrics_comparison.png', dpi=150)
        plt.close()
        
        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(methods))
        width = 0.35
        
        tp_vals = [metrics[m]['tp'] for m in methods]
        fp_vals = [metrics[m]['fp'] for m in methods]
        fn_vals = [metrics[m]['fn'] for m in methods]
        
        ax.bar(x - width/2, tp_vals, width, label='True Positives', color='#22c55e')
        ax.bar(x, fp_vals, width, label='False Positives', color='#ef4444')
        ax.bar(x + width/2, fn_vals, width, label='False Negatives', color='#f97316')
        
        ax.set_xticks(x)
        ax.set_xticklabels(methods)
        ax.set_ylabel('Count')
        ax.set_title('Confusion Matrix Components')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(output_dir / 'confusion_components.png', dpi=150)
        plt.close()
        
        print(f"Plots saved to {output_dir}")


async def main():
    print("=" * 60)
    print("SKYGUARD AI - Model Evaluation")
    print("=" * 60)
    
    await init_db()
    
    evaluator = ModelEvaluator()
    await evaluator.load_models()
    
    async with AsyncSessionLocal() as db:
        df, ground_truth = await evaluator.generate_test_data(db, days=3)
        
        X_scaled, indices = evaluator.prepare_features(df)
        
        predictions = evaluator.run_detection(X_scaled, df, indices)
        
        metrics = evaluator.evaluate(predictions, ground_truth, df)
        
        print("\n=== Evaluation Results ===")
        for method, m in metrics.items():
            print(f"\n{method.upper()}:")
            for k, v in m.items():
                print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
        
        output_dir = Path("evaluation_results")
        evaluator.plot_results(metrics, output_dir)
        
        with open(output_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"\nResults saved to {output_dir}/metrics.json")


if __name__ == "__main__":
    asyncio.run(main())