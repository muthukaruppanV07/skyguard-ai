import asyncio
import json
from typing import List, Dict, Any
from backend.simulation.anomaly_injector import AnomalyInjector
from backend.simulation.esp32_simulator import ESP32Fleet, ESP32Config
from backend.data.imd_sample_generator import generate_imd_sample_csv, generate_monsoon_period_data
from backend.anomaly.onnx_export import export_all_models
from backend.anomaly.lstm_autoencoder import create_lstm_autoencoder
from backend.simulation.esp32_simulator import ESP32Fleet
import pandas as pd


class AdvancedSIHDemo:
    def __init__(self, injector: AnomalyInjector):
        self.injector = injector
        self.esp32_fleet = None
        self.demo_steps = [
            {
                "phase": "Setup",
                "name": "Initialize Advanced Features",
                "description": "Export models to ONNX, load LSTM Autoencoder, generate IMD sample data",
                "action": "initialize_advanced",
                "duration": 5,
            },
            {
                "phase": "ESP32",
                "name": "Start ESP32 Fleet",
                "description": "Launch 8 ESP32 devices publishing sensor data via MQTT",
                "action": "start_esp32_fleet",
                "duration": 3,
            },
            {
                "phase": "IMD Data",
                "name": "Load Real IMD Sample Data",
                "description": "Load pre-generated IMD sample data with monsoon/heatwave/cyclone patterns",
                "action": "load_imd_data",
                "duration": 3,
            },
            {
                "phase": "Demo",
                "name": "Healthy Baseline",
                "description": "Show all 8 stations operating normally with real-time ESP32 data",
                "action": "baseline",
                "duration": 3,
            },
            {
                "phase": "Demo",
                "name": "Temperature Spike",
                "description": "Inject sudden temperature spike (AWS001: 31.5°C → 55.2°C)",
                "action": "inject",
                "params": {"station_id": "AWS001", "fault_type": "TEMPERATURE_SPIKE", "params": {"magnitude": 23.7}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "ESP32 Battery Low",
                "description": "Simulate ESP32 battery depletion on AWS003",
                "action": "esp32_anomaly",
                "params": {"anomaly_type": "battery_low", "device_ids": ["ESP32-003"]},
                "duration": 3,
            },
            {
                "phase": "Demo",
                "name": "Sensor Drift",
                "description": "Gradual temperature drift (+1.5°C/hour for 30 min)",
                "action": "inject",
                "params": {"station_id": "AWS002", "fault_type": "TEMPERATURE_DRIFT", "params": {"rate": 1.5, "duration_minutes": 30}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "Frozen Sensor",
                "description": "Humidity sensor stuck at constant value for 20 minutes",
                "action": "inject",
                "params": {"station_id": "AWS003", "fault_type": "FROZEN_SENSOR", "params": {"sensor": "humidity", "duration_minutes": 20}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "ESP32 Signal Lost",
                "description": "Simulate ESP32 signal loss on AWS004",
                "action": "esp32_anomaly",
                "params": {"anomaly_type": "signal_lost", "device_ids": ["ESP32-004"]},
                "duration": 3,
            },
            {
                "phase": "Demo",
                "name": "Communication Failure",
                "description": "Data transmission failure for 10 minutes",
                "action": "inject",
                "params": {"station_id": "AWS004", "fault_type": "COMMUNICATION_FAILURE", "params": {"duration_minutes": 10}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "Multivariate Inconsistency",
                "description": "Temperature rises but humidity doesn't follow physical relationship",
                "action": "inject",
                "params": {"station_id": "AWS005", "fault_type": "MULTIVARIATE_INCONSISTENCY", "params": {}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "Pressure Spike",
                "description": "Sudden pressure increase (1013 → 1048 hPa)",
                "action": "inject",
                "params": {"station_id": "AWS006", "fault_type": "PRESSURE_SPIKE", "params": {"magnitude": 35}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "ESP32 Sensor Fault",
                "description": "Simulate ESP32 sensor malfunction on AWS007",
                "action": "esp32_anomaly",
                "params": {"anomaly_type": "temperature_spike", "device_ids": ["ESP32-007"]},
                "duration": 3,
            },
            {
                "phase": "Demo",
                "name": "Humidity Drop",
                "description": "Sudden humidity drop (65% → 25%)",
                "action": "inject",
                "params": {"station_id": "AWS007", "fault_type": "HUMIDITY_SPIKE", "params": {"magnitude": 40, "direction": -1}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "Sensor Degradation",
                "description": "Increasing noise across all sensors on AWS008",
                "action": "inject",
                "params": {"station_id": "AWS008", "fault_type": "SENSOR_DEGRADATION", "params": {"factor": 4.0}},
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "ONNX Model Export",
                "description": "Export Isolation Forest, Autoencoder, and Scaler to ONNX format",
                "action": "export_onnx",
                "duration": 5,
            },
            {
                "phase": "Demo",
                "name": "LSTM Autoencoder Training",
                "description": "Train LSTM Autoencoder on temporal sequences",
                "action": "train_lstm",
                "duration": 10,
            },
            {
                "phase": "Demo",
                "name": "Load IMD Monsoon Data",
                "description": "Load pre-generated monsoon period data with 30-min intervals",
                "action": "load_monsoon",
                "duration": 3,
            },
            {
                "phase": "Demo",
                "name": "Reset All",
                "description": "Clear all anomalies, stop ESP32 fleet, return to healthy baseline",
                "action": "reset_all",
                "duration": 3,
            },
        ]

    async def run_step(self, step_index: int) -> Dict[str, Any]:
        if step_index >= len(self.demo_steps):
            return {"status": "complete", "message": "Advanced demo finished"}
        
        step = self.demo_steps[step_index]
        
        if step["action"] == "initialize_advanced":
            return await self._initialize_advanced(step["duration"])
        elif step["action"] == "start_esp32_fleet":
            return await self._start_esp32_fleet(step["duration"])
        elif step["action"] == "load_imd_data":
            return await self._load_imd_data(step["duration"])
        elif step["action"] == "baseline":
            return await self._run_baseline(step["duration"])
        elif step["action"] == "inject":
            return await self._inject_anomaly(step["params"], step["duration"])
        elif step["action"] == "esp32_anomaly":
            return await self._esp32_anomaly(step["params"], step["duration"])
        elif step["action"] == "load_imd_data":
            return await self._load_imd_data(step["duration"])
        elif step["action"] == "load_monsoon":
            return await self._load_monsoon(step["duration"])
        elif step["action"] == "export_onnx":
            return await self._export_onnx(step["duration"])
        elif step["action"] == "train_lstm":
            return await self._train_lstm(step["duration"])
        elif step["action"] == "reset_all":
            return await self._reset_all(step["duration"])
        
        return {"status": "unknown"}

    async def _initialize_advanced(self, duration: int) -> Dict[str, Any]:
        print("Initializing advanced features...")
        
        print("  Exporting models to ONNX...")
        try:
            from backend.anomaly.onnx_export import export_all_models
            paths = export_all_models()
            onnx_result = {"status": "success", "paths": {k: str(v) for k, v in paths.items()}}
        except Exception as e:
            onnx_result = {"status": "error", "error": str(e)}
        
        print("  Initializing LSTM Autoencoder...")
        try:
            from backend.anomaly.lstm_autoencoder import create_lstm_autoencoder
            lstm_model = create_lstm_autoencoder()
            lstm_result = {"status": "initialized"}
        except Exception as e:
            lstm_result = {"status": "error", "error": str(e)}
        
        print("  Generating IMD sample data...")
        try:
            from backend.data.imd_sample_generator import generate_imd_sample_csv
            generate_imd_sample_csv(
                output_dir="data/imd_sample",
                start_date="2024-06-01",
                end_date="2024-06-30",
                interval_minutes=60
            )
            imd_result = {"status": "generated", "path": "data/imd_sample/"}
        except Exception as e:
            imd_result = {"status": "error", "error": str(e)}
        
        await asyncio.sleep(duration)
        return {
            "status": "done",
            "step": "Initialize Advanced Features",
            "onnx": onnx_result,
            "lstm": lstm_result,
            "imd_data": imd_result
        }

    async def _start_esp32_fleet(self, duration: int) -> Dict[str, Any]:
        print("Starting ESP32 fleet...")
        self.esp32_fleet = ESP32Fleet()
        
        for i in range(8):
            device_id = f"ESP32-{i+1:03d}"
            station_id = f"AWS{i+1:03d}"
            self.esp32_fleet.add_device(device_id, station_id)
        
        await self.esp32_fleet.connect_all()
        await self.esp32_fleet.start_all()
        
        await asyncio.sleep(duration)
        
        return {
            "status": "done",
            "step": "Start ESP32 Fleet",
            "devices": len(self.esp32_fleet.devices),
            "fleet_status": self.esp32_fleet.get_fleet_status()
        }

    async def _load_imd_data(self, duration: int) -> Dict[str, Any]:
        print("Loading IMD sample data...")
        try:
            from backend.data.imd_sample_generator import generate_imd_sample_csv
            generate_imd_sample_csv(
                output_dir="data/imd_sample",
                start_date="2024-06-01",
                end_date="2024-06-30",
                interval_minutes=60
            )
            result = {"status": "loaded", "path": "data/imd_sample/"}
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        
        await asyncio.sleep(duration)
        return {"status": "done", "step": "Load IMD Sample Data", "result": result}

    async def _load_monsoon(self, duration: int) -> Dict[str, Any]:
        print("Loading monsoon period data...")
        try:
            from backend.data.imd_sample_generator import generate_monsoon_period_data
            monsoon_df = generate_monsoon_period_data()
            monsoon_df.to_csv("data/imd_sample/monsoon_2024.csv", index=False)
            result = {"status": "loaded", "records": len(monsoon_df), "path": "data/imd_sample/monsoon_2024.csv"}
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        
        await asyncio.sleep(duration)
        return {"status": "done", "step": "Load Monsoon Data", "result": result}

    async def _run_baseline(self, duration: int) -> Dict[str, Any]:
        for sid in self.injector.simulator.stations:
            self.injector.simulator.unfreeze_sensor(sid)
            self.injector.simulator.clear_comm_failure(sid)
            self.injector.simulator.apply_drift(sid, 0, 0, 0)
            self.injector.simulator.set_degradation(sid, 1.0)
        self.injector.clear_history()
        
        await asyncio.sleep(duration)
        return {"status": "done", "step": "Healthy Baseline"}

    async def _inject_anomaly(self, params: Dict, duration: int) -> Dict[str, Any]:
        result = await self.injector.inject(**params)
        await asyncio.sleep(duration)
        return {"status": "injected", "result": result}

    async def _esp32_anomaly(self, params: Dict, duration: int) -> Dict[str, Any]:
        if not self.esp32_fleet:
            return {"status": "error", "error": "ESP32 fleet not started"}
        
        self.esp32_fleet.inject_fleet_anomaly(
            params["anomaly_type"],
            params.get("device_ids"),
            **params.get("params", {})
        )
        
        await asyncio.sleep(duration)
        return {"status": "injected", "anomaly": params["anomaly_type"]}

    async def _export_onnx(self, duration: int) -> Dict[str, Any]:
        print("Exporting models to ONNX...")
        try:
            from backend.anomaly.onnx_export import export_all_models
            paths = export_all_models()
            
            from backend.anomaly.onnx_export import ONNXExporter
            import numpy as np
            exporter = ONNXExporter()
            test_input = np.random.randn(1, 30).astype(np.float32)
            
            validation_results = {}
            for name, path in paths.items():
                validation_results[name] = exporter.validate_onnx(path, np.random.randn(1, 30).astype(np.float32))
            
            result = {"status": "success", "paths": {k: str(v) for k, v in paths.items()}, "validation": validation_results}
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        
        await asyncio.sleep(duration)
        return {"status": "done", "step": "ONNX Model Export", "result": result}

    async def _train_lstm(self, duration: int) -> Dict[str, Any]:
        print("Training LSTM Autoencoder...")
        try:
            from backend.anomaly.lstm_autoencoder import create_lstm_autoencoder
            import numpy as np
            
            lstm_model = create_lstm_autoencoder(sequence_length=20)
            
            dummy_data = np.random.randn(1000, 3).astype(np.float32)
            dummy_data[:, 0] = 25 + 5 * np.sin(np.linspace(0, 4*np.pi, 1000))
            dummy_data[:, 1] = 1013 + 2 * np.sin(np.linspace(0, 2*np.pi, 1000))
            dummy_data[:, 2] = 60 + 20 * np.cos(np.linspace(0, 4*np.pi, 1000))
            
            lstm_model.fit(dummy_data, epochs=20, batch_size=32, verbose=False)
            lstm_model.save()
            
            test_errors = lstm_model.reconstruction_error(dummy_data[:100])
            
            result = {
                "status": "trained",
                "epochs": 20,
                "final_train_loss": lstm_model.train_losses[-1] if lstm_model.train_losses else 0,
                "test_reconstruction_error_mean": float(np.mean(test_errors)),
                "model_path": "models/lstm_autoencoder.pt"
            }
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        
        await asyncio.sleep(duration)
        return {"status": "done", "step": "LSTM Autoencoder Training", "result": result}

    async def _reset_all(self, duration: int) -> Dict[str, Any]:
        if self.esp32_fleet:
            await self.esp32_fleet.stop_all()
            self.esp32_fleet = None
        
        for sid in self.injector.simulator.stations:
            self.injector.simulator.unfreeze_sensor(sid)
            self.injector.simulator.clear_comm_failure(sid)
            self.injector.simulator.apply_drift(sid, 0, 0, 0)
            self.injector.simulator.set_degradation(sid, 1.0)
        self.injector.clear_history()
        
        await asyncio.sleep(duration)
        return {"status": "reset", "step": "Reset All"}

    async def run_full_demo(self) -> List[Dict[str, Any]]:
        results = []
        for i in range(len(self.demo_steps)):
            result = await self.run_step(i)
            results.append(result)
            print(f"Step {i+1}/{len(self.demo_steps)}: {result.get('step', 'N/A')} - {result.get('status', 'N/A')}")
        return results

    def get_steps(self) -> List[Dict]:
        return [
            {
                "index": i,
                "phase": step.get("phase", "Demo"),
                "name": step["name"],
                "description": step["description"],
                "duration": step["duration"],
            }
            for i, step in enumerate(self.demo_steps)
        ]

    async def run_step_by_action(self, action: str, params: Dict = None) -> Dict[str, Any]:
        params = params or {}
        action_map = {
            "initialize_advanced": lambda: self._initialize_advanced(5),
            "start_esp32_fleet": lambda: self._start_esp32_fleet(3),
            "load_imd_data": lambda: self._load_imd_data(3),
            "load_monsoon": lambda: self._load_monsoon(3),
            "baseline": lambda: self._run_baseline(3),
            "inject": lambda: self._inject_anomaly(params, 5),
            "esp32_anomaly": lambda: self._esp32_anomaly(params, 3),
            "export_onnx": lambda: self._export_onnx(5),
            "train_lstm": lambda: self._train_lstm(10),
            "load_monsoon": lambda: self._load_monsoon(3),
            "reset_all": lambda: self._reset_all(3),
        }
        
        if action in action_map:
            return await action_map[action]()
        
        return {"status": "error", "error": f"Unknown action: {action}"}


class QuickAdvancedDemo:
    def __init__(self, injector: AnomalyInjector):
        self.injector = injector
        self.demo_steps = [
            {"name": "ONNX Export", "action": "export_onnx", "description": "Export models to ONNX for edge deployment"},
            {"name": "LSTM Autoencoder", "action": "train_lstm", "description": "Train LSTM Autoencoder for temporal patterns"},
            {"name": "ESP32 Fleet", "action": "start_esp32_fleet", "description": "Launch 8 ESP32 devices via MQTT"},
            {"name": "IMD Sample Data", "action": "load_imd_data", "description": "Load realistic IMD sample data"},
            {"name": "Temperature Spike", "action": "inject", "params": {"station_id": "AWS001", "fault_type": "TEMPERATURE_SPIKE", "params": {"magnitude": 25}}, "description": "Sudden temperature spike"},
            {"name": "ESP32 Battery Low", "action": "esp32_anomaly", "params": {"anomaly_type": "battery_low", "device_ids": ["ESP32-001"]}, "description": "ESP32 battery depletion"},
            {"name": "ESP32 Signal Lost", "action": "esp32_anomaly", "params": {"anomaly_type": "signal_lost", "device_ids": ["ESP32-002"]}, "description": "ESP32 signal loss"},
            {"name": "ONNX Validation", "action": "export_onnx", "description": "Validate ONNX model inference"},
            {"name": "Reset All", "action": "reset_all", "description": "Clear all anomalies and stop ESP32 fleet"},
        ]

    async def run_step(self, step_index: int) -> Dict[str, Any]:
        if step_index >= len(self.demo_steps):
            return {"status": "complete"}
        
        step = self.demo_steps[step_index]
        
        demo = AdvancedSIHDemo(self.injector)
        
        if step["action"] == "export_onnx":
            return await demo._export_onnx(3)
        elif step["action"] == "train_lstm":
            return await demo._train_lstm(10)
        elif step["action"] == "start_esp32_fleet":
            return await demo._start_esp32_fleet(3)
        elif step["action"] == "load_imd_data":
            return await demo._load_imd_data(3)
        elif step["action"] == "inject":
            return await demo._inject_anomaly(step.get("params", {}), 3)
        elif step["action"] == "esp32_anomaly":
            return await demo._esp32_anomaly(step.get("params", {}), 3)
        elif step["action"] == "load_monsoon":
            return await demo._load_monsoon(3)
        elif step["action"] == "reset_all":
            return await demo._reset_all(3)
        
        return {"status": "unknown"}

    def get_steps(self) -> List[Dict]:
        return [
            {"index": i, "name": step["name"], "description": step["description"]}
            for i, step in enumerate(self.demo_steps)
        ]