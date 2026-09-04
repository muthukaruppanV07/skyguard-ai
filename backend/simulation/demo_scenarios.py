import asyncio
from typing import List, Dict, Any
from backend.simulation.anomaly_injector import AnomalyInjector, DemoScenario


class SIHDemoScenario:
    def __init__(self, injector: AnomalyInjector):
        self.injector = injector
        self.demo_steps = [
            {
                "name": "Healthy Network Baseline",
                "description": "Show all 8 stations operating normally",
                "action": "baseline",
                "duration": 3,
            },
            {
                "name": "Temperature Spike - AWS001",
                "description": "Inject sudden temperature spike (31.5°C → 55.2°C)",
                "action": "inject",
                "params": {"station_id": "AWS001", "fault_type": "TEMPERATURE_SPIKE", "params": {"magnitude": 23.7}},
                "duration": 5,
            },
            {
                "name": "Sensor Drift - AWS002",
                "description": "Gradual temperature drift (+1.5°C/hour for 30 min)",
                "action": "inject",
                "params": {"station_id": "AWS002", "fault_type": "TEMPERATURE_DRIFT", "params": {"rate": 1.5, "duration_minutes": 30}},
                "duration": 5,
            },
            {
                "name": "Frozen Sensor - AWS003",
                "description": "Humidity sensor stuck at constant value for 20 minutes",
                "action": "inject",
                "params": {"station_id": "AWS003", "fault_type": "FROZEN_SENSOR", "params": {"sensor": "humidity", "duration_minutes": 20}},
                "duration": 5,
            },
            {
                "name": "Communication Failure - AWS004",
                "description": "Data transmission failure for 10 minutes",
                "action": "inject",
                "params": {"station_id": "AWS004", "fault_type": "COMMUNICATION_FAILURE", "params": {"duration_minutes": 10}},
                "duration": 5,
            },
            {
                "name": "Multivariate Inconsistency - AWS005",
                "description": "Temperature rises but humidity doesn't follow physical relationship",
                "action": "inject",
                "params": {"station_id": "AWS005", "fault_type": "MULTIVARIATE_INCONSISTENCY", "params": {}},
                "duration": 5,
            },
            {
                "name": "Pressure Spike - AWS006",
                "description": "Sudden pressure increase (1013 → 1048 hPa)",
                "action": "inject",
                "params": {"station_id": "AWS006", "fault_type": "PRESSURE_SPIKE", "params": {"magnitude": 35}},
                "duration": 5,
            },
            {
                "name": "Humidity Drop - AWS007",
                "description": "Sudden humidity drop (65% → 25%)",
                "action": "inject",
                "params": {"station_id": "AWS007", "fault_type": "HUMIDITY_SPIKE", "params": {"magnitude": 40, "direction": -1}},
                "duration": 5,
            },
            {
                "name": "Sensor Degradation - AWS008",
                "description": "Increasing noise across all sensors",
                "action": "inject",
                "params": {"station_id": "AWS008", "fault_type": "SENSOR_DEGRADATION", "params": {"factor": 4.0}},
                "duration": 5,
            },
            {
                "name": "Reset to Healthy",
                "description": "Clear all anomalies, return to normal operation",
                "action": "reset",
                "duration": 2,
            },
        ]

    async def run_step(self, step_index: int) -> Dict[str, Any]:
        if step_index >= len(self.demo_steps):
            return {"status": "complete", "message": "Demo finished"}
        
        step = self.demo_steps[step_index]
        
        if step["action"] == "baseline":
            for sid in self.injector.simulator.stations:
                self.injector.simulator.unfreeze_sensor(sid)
                self.injector.simulator.clear_comm_failure(sid)
                self.injector.simulator.apply_drift(sid, 0, 0, 0)
                self.injector.simulator.set_degradation(sid, 1.0)
            self.injector.clear_history()
            await asyncio.sleep(step["duration"])
            return {"status": "done", "step": step["name"]}
        
        elif step["action"] == "inject":
            result = await self.injector.inject(**step["params"])
            await asyncio.sleep(step["duration"])
            return {"status": "injected", "step": step["name"], "result": result}
        
        elif step["action"] == "reset":
            await self.injector.simulator.reset()
            self.injector.clear_history()
            await asyncio.sleep(step["duration"])
            return {"status": "reset", "step": step["name"]}
        
        return {"status": "unknown"}

    async def run_full_demo(self) -> List[Dict[str, Any]]:
        results = []
        for i in range(len(self.demo_steps)):
            result = await self.run_step(i)
            results.append(result)
        return results

    def get_steps(self) -> List[Dict]:
        return [
            {
                "index": i,
                "name": step["name"],
                "description": step["description"],
                "duration": step["duration"],
            }
            for i, step in enumerate(self.demo_steps)
        ]


class QuickDemoScenario:
    def __init__(self, injector: AnomalyInjector):
        self.injector = injector
        self.demo_steps = [
            {
                "name": "Temperature Spike",
                "action": "inject",
                "params": {"station_id": "AWS001", "fault_type": "TEMPERATURE_SPIKE", "params": {"magnitude": 25}},
                "description": "Sudden temperature spike from 31°C to 56°C",
            },
            {
                "name": "Pressure Spike",
                "action": "inject",
                "params": {"station_id": "AWS002", "fault_type": "PRESSURE_SPIKE", "params": {"magnitude": 40}},
                "description": "Sudden pressure spike",
            },
            {
                "name": "Frozen Sensor",
                "action": "inject",
                "params": {"station_id": "AWS003", "fault_type": "FROZEN_SENSOR", "params": {"sensor": "temperature", "duration_minutes": 15}},
                "description": "Temperature sensor frozen",
            },
            {
                "name": "Multivariate Anomaly",
                "action": "inject",
                "params": {"station_id": "AWS004", "fault_type": "MULTIVARIATE_INCONSISTENCY", "params": {}},
                "description": "T-H-P relationship violation",
            },
            {
                "name": "Reset",
                "action": "reset",
                "description": "Clear all anomalies",
            },
        ]

    async def run_step(self, step_index: int) -> Dict[str, Any]:
        if step_index >= len(self.demo_steps):
            return {"status": "complete"}
        
        step = self.demo_steps[step_index]
        
        if step["action"] == "inject":
            result = await self.injector.inject(**step["params"])
            return {"status": "injected", "step": step["name"], "result": result}
        elif step["action"] == "reset":
            for sid in self.injector.simulator.stations:
                self.injector.simulator.unfreeze_sensor(sid)
                self.injector.simulator.clear_comm_failure(sid)
                self.injector.simulator.apply_drift(sid, 0, 0, 0)
                self.injector.simulator.set_degradation(sid, 1.0)
            self.injector.clear_history()
            return {"status": "reset", "step": step["name"]}
        
        return {"status": "unknown"}

    def get_steps(self) -> List[Dict]:
        return [
            {"index": i, "name": step["name"], "description": step["description"]}
            for i, step in enumerate(self.demo_steps)
        ]