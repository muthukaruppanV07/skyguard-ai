import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import joblib
import torch
from sqlalchemy import select

from backend.config import settings
from backend.database.session import init_db, AsyncSessionLocal
from backend.models import Station, Reading
from backend.simulation.aws_simulator import AWSSimulator, run_historical_simulation
from backend.preprocessing import FeatureEngineer, FeatureScaler
from backend.anomaly import IsolationForestModel, AutoencoderModel
from backend.database.repositories import ModelRunRepository
from backend.models.model_run import ModelType


async def generate_training_data(db, days: int = 30) -> pd.DataFrame:
    print(f"Generating {days} days of training data...")
    
    await run_historical_simulation(days=days, interval_minutes=5)
    
    stations = await db.execute(
        select(Station).where(Station.status == "ACTIVE")
    )
    station_list = stations.scalars().all()
    
    all_readings = []
    for station in station_list:
        readings = await db.execute(
            select(Reading)
            .where(Reading.station_id == station.id)
            .order_by(Reading.timestamp)
        )
        for r in readings.scalars().all():
            all_readings.append({
                'station_id': r.station_id,
                'timestamp': r.timestamp,
                'temperature': r.temperature,
                'pressure': r.pressure,
                'humidity': r.humidity,
            })
    
    df = pd.DataFrame(all_readings)
    print(f"Generated {len(df)} readings from {len(station_list)} stations")
    return df


def prepare_features(df: pd.DataFrame) -> np.ndarray:
    feature_engineer = FeatureEngineer()
    
    all_features = []
    for station_id in df['station_id'].unique():
        station_df = df[df['station_id'] == station_id].sort_values('timestamp')
        readings = station_df.to_dict('records')
        
        features_df = feature_engineer.engineer_features(
            readings=readings,
            station_id=station_id,
        )
        model_features = feature_engineer.get_model_features(features_df)
        all_features.append(model_features)
    
    X = np.vstack(all_features)
    print(f"Prepared feature matrix: {X.shape}")
    return X


async def train_isolation_forest(X: np.ndarray) -> IsolationForestModel:
    print("Training Isolation Forest...")
    model = IsolationForestModel()
    model.fit(X)
    model.save()
    print("Isolation Forest trained and saved")
    return model


async def train_autoencoder(X: np.ndarray) -> AutoencoderModel:
    print("Training Autoencoder...")
    model = AutoencoderModel(input_dim=X.shape[1])
    model.fit(X, epochs=settings.AE_EPOCHS, batch_size=settings.AE_BATCH_SIZE)
    model.save()
    print("Autoencoder trained and saved")
    return model


async def train_scaler(X: np.ndarray) -> FeatureScaler:
    print("Fitting scaler...")
    scaler = FeatureScaler()
    scaler.fit(X)
    scaler.save()
    print("Scaler fitted and saved")
    return scaler


async def evaluate_models(X: np.ndarray, if_model: IsolationForestModel, ae_model: AutoencoderModel):
    print("\n=== Model Evaluation ===")
    
    if_scores = if_model.predict_score(X)
    ae_scores = ae_model.reconstruction_error(X)
    
    print(f"Isolation Forest scores - Mean: {if_scores.mean():.2f}, Std: {if_scores.std():.2f}")
    print(f"Autoencoder scores - Mean: {ae_scores.mean():.2f}, Std: {ae_scores.std():.2f}")
    
    if_threshold = np.percentile(if_scores, 99)
    ae_threshold = np.percentile(ae_scores, 99)
    
    print(f"IF 99th percentile threshold: {if_threshold:.2f}")
    print(f"AE 99th percentile threshold: {ae_threshold:.2f}")
    
    return {
        'if_threshold': float(if_threshold),
        'ae_threshold': float(ae_threshold),
        'if_mean': float(if_scores.mean()),
        'if_std': float(if_scores.std()),
        'ae_mean': float(ae_scores.mean()),
        'ae_std': float(ae_scores.std()),
    }


async def save_model_metrics(metrics: dict):
    async with AsyncSessionLocal() as db:
        repo = ModelRunRepository(db)
        
        if_run = ModelRun(
            model_name=ModelType.ISOLATION_FOREST,
            model_version=settings.MODEL_VERSION,
            training_data_hash="synthetic_v1",
        )
        if_run.set_metrics({
            'threshold': metrics['if_threshold'],
            'mean_score': metrics['if_mean'],
            'std_score': metrics['if_std'],
        })
        await repo.create(if_run)
        
        ae_run = ModelRun(
            model_name=ModelType.AUTOENCODER,
            model_version=settings.MODEL_VERSION,
            training_data_hash="synthetic_v1",
        )
        ae_run.set_metrics({
            'threshold': metrics['ae_threshold'],
            'mean_score': metrics['ae_mean'],
            'std_score': metrics['ae_std'],
            'epochs': settings.AE_EPOCHS,
            'batch_size': settings.AE_BATCH_SIZE,
        })
        await repo.create(ae_run)
        
        await db.commit()
        print("Model metrics saved to database")


async def main():
    print("=" * 60)
    print("SKYGUARD AI - Model Training Pipeline")
    print("=" * 60)
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        df = await generate_training_data(db, days=30)
        
        X = prepare_features(df)
        
        scaler = await train_scaler(X)
        X_scaled = scaler.transform(X)
        
        if_model = await train_isolation_forest(X_scaled)
        ae_model = await train_autoencoder(X_scaled)
        
        metrics = await evaluate_models(X_scaled, if_model, ae_model)
        
        await save_model_metrics(metrics)
        
        print("\n" + "=" * 60)
        print("Training complete!")
        print("=" * 60)
        print(f"Models saved to: {settings.MODEL_DIR}")
        print(f"Isolation Forest: {settings.ISOLATION_FOREST_PATH}")
        print(f"Autoencoder: {settings.AUTOENCODER_PATH}")
        print(f"Scaler: {settings.SCALER_PATH}")


if __name__ == "__main__":
    asyncio.run(main())