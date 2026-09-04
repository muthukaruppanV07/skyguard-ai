import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from backend.config import settings
from backend.simulation.aws_simulator import MultiStationSimulator, WeatherState
from backend.simulation.anomaly_injector import MultiStationAnomalyInjector, FaultType
from backend.preprocessing.feature_engineer import FeatureEngineer
from backend.preprocessing.data_validator import DataValidator
from backend.anomaly.isolation_forest import IsolationForestDetector
from backend.anomaly.autoencoder import AutoencoderDetector
from backend.anomaly.temporal_multivariate import TemporalAnomalyDetector, MultivariateConsistencyChecker
from backend.anomaly.spatial import SpatialConsistencyChecker
from backend.anomaly.fusion import AnomalyFusionEngine, AnomalyScore
from backend.anomaly.root_cause import RootCauseClassifier, RootCauseResult
from backend.explainability.explainability import ExplainabilityEngine, ExplanationResult
from backend.services.sensor_health import SensorHealthMonitor, SensorHealthResult
from backend.database.session import get_db
from backend.database.models import WeatherReading, Anomaly, SensorHealth as SensorHealthModel, AnomalyInjectionLog


@dataclass
class DetectionResult:
    reading: WeatherState
    anomaly_score: AnomalyScore
    root_cause: RootCauseResult
    explanation: ExplanationResult
    sensor_health: SensorHealthResult
    is_anomaly: bool


class SkyGuardDetectionService:
    def __init__(self):
        self.simulator = MultiStationSimulator(settings.STATION_IDS, seed=42)
        self.injector = MultiStationAnomalyInjector(self.simulator, seed=42)
        self.feature_engineer = FeatureEngineer()
        self.validator = DataValidator()
        self.isolation_forest = IsolationForestDetector()
        self.autoencoder = AutoencoderDetector()
        self.fusion_engine = AnomalyFusionEngine()
        self.root_cause_classifier = RootCauseClassifier()
        self.explainability = ExplainabilityEngine()
        self.health_monitor = SensorHealthMonitor(window_hours=settings.HEALTH_WINDOW_HOURS)

        self.fusion_engine.set_ml_models(self.isolation_forest, self.autoencoder)

        self.station_prev_readings: Dict[str, WeatherState] = {}
        self.last_detection_results: Dict[str, DetectionResult] = {}
        self.demo_mode = settings.DEMO_MODE

    def initialize_models(self):
        print("Loading ML models...")
        iso_loaded = self.isolation_forest.load()
        ae_loaded = self.autoencoder.load()

        if not iso_loaded:
            print("Isolation Forest not found. Training new model...")
            self._train_isolation_forest()

        if not ae_loaded:
            print("Autoencoder not found. Training new model...")
            self._train_autoencoder()

        print("Models ready.")

    def _train_isolation_forest(self):
        from backend.simulation.aws_simulator import create_historical_data
        df = create_historical_data(days=30, interval_minutes=5)
        feature_df = self.feature_engineer.engineer_batch(df)
        feature_cols = feature_df.columns.difference(["station_id", "timestamp"])
        X = feature_df[feature_cols].values
        self.isolation_forest.train(X)

    def _train_autoencoder(self):
        from backend.simulation.aws_simulator import create_historical_data
        df = create_historical_data(days=30, interval_minutes=5)
        feature_df = self.feature_engineer.engineer_batch(df)
        feature_cols = feature_df.columns.difference(["station_id", "timestamp"])
        X = feature_df[feature_cols].values
        self.autoencoder.train(X)

    def process_reading(self, station_id: str, reading: WeatherState) -> DetectionResult:
        prev_reading = self.station_prev_readings.get(station_id)
        self.station_prev_readings[station_id] = reading

        all_readings = {sid: self.simulator.simulators[sid].last_state for sid in settings.STATION_IDS}
        neighbor_readings = {k: v for k, v in all_readings.items() if k != station_id and v is not None}

        features_obj = self.feature_engineer.engineer_features(station_id, reading, neighbor_readings)
        features_array = features_obj.to_array().reshape(1, -1)

        anomaly_score = self.fusion_engine.compute_anomaly_score(
            station_id=station_id,
            reading=reading,
            prev_reading=prev_reading,
            neighbor_readings=neighbor_readings,
            features=features_array
        )

        root_cause = self.root_cause_classifier.classify(
            station_id=station_id,
            reading=reading,
            prev_reading=prev_reading,
            anomaly_score=anomaly_score,
            neighbor_readings=neighbor_readings
        )

        anomaly_score.details["root_cause"] = root_cause.root_cause.value

        explanation = self.explainability.explain_anomaly(
            anomaly_score=anomaly_score,
            root_cause=root_cause,
            reading=reading,
            prev_reading=prev_reading,
            features=features_obj,
            neighbor_readings=neighbor_readings
        )

        self.health_monitor.record_reading(station_id, reading)
        if anomaly_score.severity.value != "NORMAL":
            self.health_monitor.record_anomaly(station_id, anomaly_score)

        sensor_health = self.health_monitor.compute_health(station_id)

        is_anomaly = anomaly_score.severity.value != "NORMAL"

        result = DetectionResult(
            reading=reading,
            anomaly_score=anomaly_score,
            root_cause=root_cause,
            explanation=explanation,
            sensor_health=sensor_health,
            is_anomaly=is_anomaly
        )

        self.last_detection_results[station_id] = result
        self._persist_to_db(station_id, result)

        return result

    def _persist_to_db(self, station_id: str, result: DetectionResult):
        try:
            db = next(get_db())

            reading = result.reading
            anomaly_score = result.anomaly_score
            root_cause = result.root_cause
            explanation = result.explanation
            health = result.sensor_health

            db_reading = WeatherReading(
                station_id=station_id,
                timestamp=reading.timestamp,
                temperature=reading.temperature,
                pressure=reading.pressure,
                humidity=reading.humidity,
                is_anomalous=result.is_anomaly,
                anomaly_score=anomaly_score.final_score
            )
            db.add(db_reading)
            db.flush()

            if result.is_anomaly:
                db_anomaly = Anomaly(
                    station_id=station_id,
                    reading_id=db_reading.id,
                    timestamp=reading.timestamp,
                    parameter="multivariate",
                    observed_value=reading.temperature,
                    expected_value=explanation.expected_value,
                    corrected_value=explanation.corrected_value,
                    correction_confidence=explanation.correction_confidence,
                    anomaly_score=anomaly_score.final_score,
                    confidence=anomaly_score.confidence,
                    severity=anomaly_score.severity.value,
                    root_cause=root_cause.root_cause.value,
                    rule_score=anomaly_score.rule_score,
                    isolation_forest_score=anomaly_score.isolation_forest_score,
                    autoencoder_score=anomaly_score.autoencoder_score,
                    temporal_score=anomaly_score.temporal_score,
                    multivariate_score=anomaly_score.multivariate_score,
                    spatial_score=anomaly_score.spatial_score,
                    explanation=explanation.summary,
                    contributing_factors=str(explanation.contributing_factors),
                    recommended_action=explanation.recommended_action
                )
                db.add(db_anomaly)

            db_health = SensorHealthModel(
                station_id=station_id,
                timestamp=datetime.utcnow(),
                overall_health=health.overall_health,
                temperature_health=health.temperature_health,
                pressure_health=health.pressure_health,
                humidity_health=health.humidity_health,
                status=health.status,
                anomaly_count_24h=health.anomaly_count_24h,
                drift_score=health.drift_score,
                missing_data_ratio=health.missing_data_ratio,
                frozen_count=health.frozen_count,
                comm_failure_count=health.comm_failure_count,
                avg_reconstruction_error=health.avg_reconstruction_error,
                risk_level=health.risk_level,
                maintenance_recommendation=health.maintenance_recommendation,
                days_until_maintenance=health.days_until_maintenance
            )
            db.add(db_health)

            db.commit()
        except Exception as e:
            print(f"Error persisting to DB: {e}")

    def simulate_step(self, timestamp: Optional[datetime] = None) -> Dict[str, DetectionResult]:
        if timestamp is None:
            timestamp = datetime.utcnow()

        normal_states = self.simulator.generate_all(timestamp)
        injected_states = self.injector.apply_all_active_effects(timestamp, normal_states)

        results = {}
        for station_id in settings.STATION_IDS:
            if self.injector.injectors[station_id].is_communication_failed(station_id, timestamp):
                self.health_monitor.record_reading(station_id, injected_states[station_id], is_missing=True)
                continue

            reading = injected_states[station_id]
            results[station_id] = self.process_reading(station_id, reading)

        return results

    def inject_anomaly(self, station_id: str, fault_type: FaultType, **kwargs) -> Optional[Any]:
        return self.injector.inject_anomaly(station_id, fault_type, **kwargs)

    def get_latest_results(self) -> Dict[str, DetectionResult]:
        return self.last_detection_results

    def get_station_health(self, station_id: str) -> SensorHealthResult:
        return self.health_monitor.compute_health(station_id)

    def get_all_health(self) -> Dict[str, SensorHealthResult]:
        return self.health_monitor.get_all_station_health(settings.STATION_IDS)

    def get_injection_logs(self) -> Dict[str, List]:
        return self.injector.get_all_logs()

    def clear_demo_state(self):
        self.injector.clear_all_logs()
        self.station_prev_readings.clear()
        self.last_detection_results.clear()
        self.simulator = MultiStationSimulator(settings.STATION_IDS, seed=42)
        self.injector = MultiStationAnomalyInjector(self.simulator, seed=42)
        self.feature_engineer = FeatureEngineer()
        self.health_monitor = SensorHealthMonitor(window_hours=settings.HEALTH_WINDOW_HOURS)
        self.fusion_engine = AnomalyFusionEngine()
        self.fusion_engine.set_ml_models(self.isolation_forest, self.autoencoder)
        self.root_cause_classifier = RootCauseClassifier()
        self.explainability = ExplainabilityEngine()