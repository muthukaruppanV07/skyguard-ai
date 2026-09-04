from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Station, Reading, Anomaly, SensorHealth
from backend.models.anomaly import AnomalySeverity, RootCause
from backend.models.sensor_health import SensorType, HealthStatus
from backend.database.repositories import (
    StationRepository,
    ReadingRepository,
    AnomalyRepository,
    SensorHealthRepository,
)
from backend.preprocessing import DataValidator, FeatureEngineer, FeatureScaler
from backend.anomaly import (
    RuleEngine,
    IsolationForestModel,
    AutoencoderModel,
    TemporalAnalyzer,
    MultivariateAnalyzer,
    SpatialAnalyzer,
    AnomalyFusion,
    RootCauseClassifier,
)
from backend.explainability import TextExplainer
from backend.health import SensorHealthCalculator, MaintenanceRiskAssessor, ValueCorrector
from backend.utils.math import haversine_distance


class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.station_repo = StationRepository(db)
        self.reading_repo = ReadingRepository(db)
        self.anomaly_repo = AnomalyRepository(db)
        self.health_repo = SensorHealthRepository(db)

        self.validator = DataValidator()
        self.feature_engineer = FeatureEngineer()
        self.scaler = FeatureScaler()

        self.rule_engine = RuleEngine()
        self.if_model = IsolationForestModel()
        self.ae_model = AutoencoderModel()
        self.temporal_analyzer = TemporalAnalyzer()
        self.multivariate_analyzer = MultivariateAnalyzer()
        self.spatial_analyzer = SpatialAnalyzer()
        self.fusion = AnomalyFusion()
        self.root_cause = RootCauseClassifier()

        self.text_explainer = TextExplainer()
        self.health_calculator = SensorHealthCalculator()
        self.maintenance_assessor = MaintenanceRiskAssessor()
        self.value_corrector = ValueCorrector()

        self._models_loaded = False

    async def load_models(self):
        if self._models_loaded:
            return
        
        try:
            self.if_model.load()
            self.ae_model.load()
            self.scaler.load()
            self._models_loaded = True
        except Exception as e:
            print(f"Warning: Could not load models: {e}")

    async def process_reading(self, reading: Reading) -> Dict[str, Any]:
        await self.load_models()

        station_id = reading.station_id
        history = await self.reading_repo.get_recent_for_features(station_id, minutes=120)

        if not history:
            return {"status": "insufficient_history"}

        validation = self.validator.validate_reading(
            station_id=station_id,
            timestamp=reading.timestamp,
            temperature=reading.temperature,
            pressure=reading.pressure,
            humidity=reading.humidity,
            previous_readings=[{
                "station_id": r.station_id,
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history],
        )

        neighbor_readings = await self._get_neighbor_readings(station_id, reading.timestamp)
        station_coords = {s["station_id"]: s for s in settings.STATION_COORDS}

        rule_result = self.rule_engine.compute_score(
            current={
                "station_id": station_id,
                "timestamp": reading.timestamp,
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            },
            history=[{
                "station_id": r.station_id,
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history],
            neighbor_data=neighbor_readings,
        )

        features_df = self.feature_engineer.engineer_features(
            readings=[{
                "station_id": r.station_id,
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history] + [{
                "station_id": station_id,
                "timestamp": reading.timestamp,
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            }],
            station_id=station_id,
            neighbor_readings=neighbor_readings,
        )

        model_features = self.feature_engineer.get_model_features(features_df.iloc[[-1]])
        scaled_features = self.scaler.transform(model_features)

        if_score = 0.0
        if self.if_model.is_fitted:
            if_score = float(self.if_model.predict_score(scaled_features)[0])

        ae_score = 0.0
        if self.ae_model.is_fitted:
            ae_score = float(self.ae_model.reconstruction_error(scaled_features)[0])

        temporal_result = self.temporal_analyzer.analyze(
            current={
                "timestamp": reading.timestamp,
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            },
            history=[{
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history],
        )

        multivariate_result = self.multivariate_analyzer.analyze(
            current={
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            },
            history=[{
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history],
        )

        spatial_result = self.spatial_analyzer.analyze(
            station_id=station_id,
            current={
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            },
            neighbor_readings=neighbor_readings,
            station_coords=station_coords,
        )

        fusion_result = self.fusion.fuse(
            rule_score=rule_result["rule_score"],
            if_score=if_score,
            ae_score=ae_score,
            temporal_score=temporal_result["temporal_score"],
            multivariate_score=multivariate_result["multivariate_score"],
            spatial_score=spatial_result["spatial_score"],
        )

        root_cause_result = self.root_cause.classify(
            current={
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            },
            history=[{
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history],
            scores={
                "rule_details": rule_result,
                "temporal_details": temporal_result,
                "multivariate_details": multivariate_result,
                "components": fusion_result["components"],
            },
            spatial_score=spatial_result["spatial_score"],
            multivariate_score=multivariate_result["multivariate_score"],
        )

        correction = self.value_corrector.estimate_correction(
            station_id=station_id,
            current_time=reading.timestamp,
            observed={
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
            },
            history=[{
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history],
            neighbor_history=neighbor_readings,
        )

        explanation_data = {
            "root_cause": root_cause_result["root_cause"],
            "observed_temp": reading.temperature,
            "observed_pressure": reading.pressure,
            "observed_humidity": reading.humidity,
            "confidence": fusion_result["confidence"],
            "scores": fusion_result,
            "spatial_details": spatial_result,
            "history": [{
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in history[-10:]],
        }
        explanation_result = self.text_explainer.generate_explanation(explanation_data)

        anomaly = Anomaly(
            reading_id=reading.id,
            station_id=station_id,
            timestamp=reading.timestamp,
            anomaly_score=fusion_result["anomaly_score"],
            confidence=fusion_result["confidence"],
            severity=AnomalySeverity(fusion_result["severity"]),
            root_cause=RootCause(root_cause_result["root_cause"]),
            rule_score=rule_result["rule_score"],
            if_score=if_score,
            ae_score=ae_score,
            temporal_score=temporal_result["temporal_score"],
            multivariate_score=multivariate_result["multivariate_score"],
            spatial_score=spatial_result["spatial_score"],
            observed_temp=reading.temperature,
            observed_pressure=reading.pressure,
            observed_humidity=reading.humidity,
            expected_temp=correction["expected"]["temperature"],
            expected_pressure=correction["expected"]["pressure"],
            expected_humidity=correction["expected"]["humidity"],
            correction_confidence=correction["correction_confidence"],
            explanation=explanation_result["explanation"],
            contributing_factors=str(explanation_result["contributing_factors"]),
            model_version=settings.MODEL_VERSION,
        )

        self.db.add(anomaly)
        await self.db.flush()

        await self._update_sensor_health(station_id, anomaly)

        await self.db.commit()

        return {
            "anomaly_id": anomaly.id,
            "anomaly_score": fusion_result["anomaly_score"],
            "severity": fusion_result["severity"],
            "confidence": fusion_result["confidence"],
            "root_cause": root_cause_result["root_cause"],
            "explanation": explanation_result["explanation"],
            "correction": correction,
        }

    async def _get_neighbor_readings(
        self,
        station_id: str,
        timestamp: datetime,
    ) -> Dict[str, List[Dict]]:
        stations = await self.station_repo.get_all()
        target = next((s for s in stations if s.id == station_id), None)
        if not target:
            return {}

        neighbors = []
        for s in stations:
            if s.id == station_id:
                continue
            dist = haversine_distance(
                target.latitude, target.longitude,
                s.latitude, s.longitude
            )
            if dist <= settings.SPATIAL_MAX_DISTANCE_KM:
                neighbors.append((s.id, dist))

        neighbors.sort(key=lambda x: x[1])
        neighbors = neighbors[:settings.SPATIAL_K_NEIGHBORS]

        result = {}
        for n_id, _ in neighbors:
            readings = await self.reading_repo.get_by_station_time_range(
                n_id,
                timestamp - timedelta(minutes=60),
                timestamp,
                limit=100,
            )
            result[n_id] = [{
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity,
            } for r in readings]

        return result

    async def _update_sensor_health(self, station_id: str, anomaly: Anomaly):
        for sensor_type in SensorType:
            health_data = await self._compute_sensor_health(station_id, sensor_type, anomaly)
            health = SensorHealth(
                station_id=station_id,
                sensor_type=sensor_type,
                **health_data,
            )
            await self.health_repo.upsert(health)

    async def _compute_sensor_health(
        self,
        station_id: str,
        sensor_type: SensorType,
        latest_anomaly: Anomaly,
    ) -> Dict[str, Any]:
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        cutoff_7d = datetime.utcnow() - timedelta(days=7)

        anomalies_24h = await self.anomaly_repo.get_recent(station_id, hours=24)
        anomalies_7d = await self.anomaly_repo.get_recent(station_id, hours=168)

        sensor_anomalies_24h = [a for a in anomalies_24h if self._anomaly_affects_sensor(a, sensor_type)]
        sensor_anomalies_7d = [a for a in anomalies_7d if self._anomaly_affects_sensor(a, sensor_type)]

        drift_detected = any(
            a.root_cause == RootCause.SENSOR_DRIFT for a in sensor_anomalies_7d
        )
        frozen_count = sum(
            1 for a in sensor_anomalies_7d if a.root_cause == RootCause.FROZEN_SENSOR
        )
        missing_count = sum(
            1 for a in sensor_anomalies_7d if a.root_cause == RootCause.MISSING_DATA
        )
        comm_count = sum(
            1 for a in sensor_anomalies_7d if a.root_cause == RootCause.COMMUNICATION_FAILURE
        )

        return {
            "anomaly_count_24h": len(sensor_anomalies_24h),
            "anomaly_count_7d": len(sensor_anomalies_7d),
            "drift_detected": drift_detected,
            "frozen_count": frozen_count,
            "missing_count": missing_count,
            "comm_failure_count": comm_count,
            "reconstruction_error_avg": 0.0,
        }

    def _anomaly_affects_sensor(self, anomaly: Anomaly, sensor_type: SensorType) -> bool:
        if anomaly.root_cause in [RootCause.TEMPERATURE_SPIKE, RootCause.SENSOR_DRIFT]:
            return sensor_type == SensorType.TEMPERATURE
        if anomaly.root_cause in [RootCause.PRESSURE_SPIKE]:
            return sensor_type == SensorType.PRESSURE
        if anomaly.root_cause in [RootCause.HUMIDITY_SPIKE]:
            return sensor_type == SensorType.HUMIDITY
        if anomaly.root_cause in [RootCause.FROZEN_SENSOR, RootCause.MISSING_DATA, RootCause.COMMUNICATION_FAILURE]:
            return True
        return sensor_type in [SensorType.TEMPERATURE, SensorType.PRESSURE, SensorType.HUMIDITY]

    async def get_live_snapshot(self) -> Dict[str, Any]:
        stations = await self.station_repo.get_active()
        latest_readings = await self.reading_repo.get_latest_all_stations()
        health_summary = await self.health_repo.get_network_summary()

        station_data = {}
        for reading in latest_readings:
            anomaly = await self.anomaly_repo.get_by_reading_id(reading.id)
            health = health_summary["stations"].get(reading.station_id, {})
            
            station_data[reading.station_id] = {
                "station_id": reading.station_id,
                "timestamp": reading.timestamp.isoformat(),
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity,
                "anomaly_score": anomaly.anomaly_score if anomaly else 0,
                "confidence": anomaly.confidence if anomaly else 1.0,
                "severity": anomaly.severity.value if anomaly else "NORMAL",
                "root_cause": anomaly.root_cause.value if anomaly else "NORMAL",
                "health": {
                    "temperature": health.get("TEMPERATURE", {}).get("score", 100),
                    "pressure": health.get("PRESSURE", {}).get("score", 100),
                    "humidity": health.get("HUMIDITY", {}).get("score", 100),
                },
            }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stations": station_data,
            "network_health": health_summary["overall_avg"],
        }