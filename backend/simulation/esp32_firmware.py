import asyncio
import json
import random
import time
import hashlib
import struct
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import paho.mqtt.client as mqtt
from backend.config import settings
from backend.simulation.aws_simulator import AWSSimulator


class ESP32State(Enum):
    BOOTING = "booting"
    INITIALIZING = "initializing"
    CONNECTING_WIFI = "connecting_wifi"
    CONNECTING_MQTT = "connecting_mqtt"
    RUNNING = "running"
    SLEEPING = "sleeping"
    OTA_UPDATE = "ota_update"
    ERROR = "error"
    CALIBRATING = "calibrating"


class SensorType(Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    HUMIDITY = "humidity"
    BATTERY = "battery"
    SIGNAL = "signal"


class SensorStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    CALIBRATING = "calibrating"
    DISCONNECTED = "disconnected"


@dataclass
class SensorReading:
    sensor_type: SensorType
    value: float
    unit: str
    timestamp: datetime
    status: SensorStatus = SensorStatus.OK
    raw_value: int = 0
    calibrated: bool = True


@dataclass
class ESP32Telemetry:
    device_id: str
    firmware_version: str
    uptime_seconds: int
    free_heap: int
    cpu_frequency: int
    wifi_rssi: int
    wifi_channel: int
    ip_address: str
    mac_address: str
    temperature: float
    battery_voltage: float
    battery_percentage: float
    signal_strength: int
    errors_count: int
    watchdog_resets: int
    brownout_resets: int
    timestamp: datetime


@dataclass
class SensorConfig:
    sensor_type: SensorType
    gpio_pin: int
    i2c_address: int = 0
    sampling_rate_hz: float = 1.0
    calibration_offset: float = 0.0
    calibration_scale: float = 1.0
    min_value: float = -100
    max_value: float = 100
    enabled: bool = True
    calibration_points: List[Tuple[float, float]] = field(default_factory=list)


class SensorDriver:
    def __init__(self, config: SensorConfig):
        self.config = config
        self.last_reading = None
        self.reading_count = 0
        self.error_count = 0
        self.last_error = None
        self.calibrated = False
        
    def read_raw(self) -> int:
        if self.config.sensor_type == SensorType.TEMPERATURE:
            return random.randint(100, 1000)
        elif self.config.sensor_type == SensorType.PRESSURE:
            return random.randint(2000, 4000)
        elif self.config.sensor_type == SensorType.HUMIDITY:
            return random.randint(1000, 3000)
        elif self.config.sensor_type == SensorType.BATTERY:
            return random.randint(3000, 4200)
        elif self.config.sensor_type == SensorType.SIGNAL:
            return random.randint(-90, -30)
        return 0
    
    def calibrate(self, raw_value: int) -> float:
        if len(self.config.calibration_points) >= 2:
            raw_vals = [p[0] for p in self.config.calibration_points]
            cal_vals = [p[1] for p in self.config.calibration_points]
            return float(np.interp(raw_value, raw_vals, cal_vals))
        
        return (raw_value * self.config.calibration_scale) + self.config.calibration_offset
    
    def read(self) -> SensorReading:
        raw = self.read_raw()
        value = self.calibrate(raw)
        
        value = max(self.config.min_value, min(self.config.max_value, value))
        
        status = SensorStatus.OK
        if value <= self.config.min_value or value >= self.config.max_value:
            status = SensorStatus.WARNING
            self.error_count += 1
            self.last_error = f"Value {value} out of range"
        
        reading = SensorReading(
            sensor_type=self.config.sensor_type,
            value=round(value, 2),
            unit=self._get_unit(),
            timestamp=datetime.utcnow(),
            status=status,
            raw_value=raw,
            calibrated=self.calibrated
        )
        
        self.last_reading = reading
        self.reading_count += 1
        return reading
    
    def _get_unit(self) -> str:
        units = {
            SensorType.TEMPERATURE: "°C",
            SensorType.PRESSURE: "hPa",
            SensorType.HUMIDITY: "%",
            SensorType.BATTERY: "V",
            SensorType.SIGNAL: "dBm"
        }
        return units.get(self.config.sensor_type, "")
    
    def apply_calibration(self, points: List[Tuple[float, float]]):
        self.config.calibration_points = points
        self.calibrated = True


class ESP32FirmwareSimulator:
    def __init__(
        self,
        device_id: str,
        station_id: str,
        mqtt_broker: str = "localhost",
        mqtt_port: int = 1883,
        wifi_ssid: str = "SKYGUARD",
        wifi_password: str = "skyguard2026"
    ):
        self.device_id = device_id
        self.station_id = station_id
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.wifi_ssid = wifi_ssid
        self.wifi_password = wifi_password
        
        self.state = ESP32State.BOOTING
        self.boot_time = time.time()
        self.firmware_version = "1.2.3"
        self.hardware_version = "ESP32-D0WDQ6-V3"
        
        self.sensors: Dict[SensorType, SensorDriver] = {}
        self._init_sensors()
        
        self.mqtt_client = mqtt.Client(client_id=self.device_id)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_publish = self._on_mqtt_publish
        
        self.mqtt_connected = False
        self.mqtt_topic = f"skyguard/{self.station_id}/{self.device_id}/data"
        self.command_topic = f"skyguard/{self.station_id}/{self.device_id}/cmd"
        self.telemetry_topic = f"skyguard/{self.station_id}/{self.device_id}/telemetry"
        
        self.aws_simulator = AWSSimulator(None)
        self.aws_simulator._init_station_states()
        
        self.telemetry_interval = 5
        self.sensor_interval = 1
        self.publish_telemetry = True
        self.publish_sensors = True
        
        self.error_log = deque(maxlen=100)
        self.command_queue = asyncio.Queue()
        
        self.ota_update = None
        self.watchdog_counter = 0
        self.last_watchdog_reset = time.time()
        
        self._register_commands()
    
    def _init_sensors(self):
        configs = {
            SensorType.TEMPERATURE: SensorConfig(
                sensor_type=SensorType.TEMPERATURE,
                gpio_pin=4,
                sampling_rate_hz=1.0,
                calibration_offset=0.0,
                calibration_scale=1.0,
                min_value=-40,
                max_value=85,
                calibration_points=[(0, -40), (4095, 85)]
            ),
            SensorType.PRESSURE: SensorConfig(
                sensor_type=SensorType.PRESSURE,
                gpio_pin=0,
                i2c_address=0x76,
                sampling_rate_hz=1.0,
                calibration_offset=0.0,
                calibration_scale=1.0,
                min_value=300,
                max_value=1100,
                calibration_points=[(0, 300), (4095, 1100)]
            ),
            SensorType.HUMIDITY: SensorConfig(
                sensor_type=SensorType.HUMIDITY,
                gpio_pin=5,
                i2c_address=0x40,
                sampling_rate_hz=1.0,
                calibration_offset=0.0,
                calibration_scale=1.0,
                min_value=0,
                max_value=100,
                calibration_points=[(0, 0), (4095, 100)]
            ),
            SensorType.BATTERY: SensorConfig(
                sensor_type=SensorType.BATTERY,
                gpio_pin=35,
                sampling_rate_hz=0.1,
                calibration_offset=0.0,
                calibration_scale=0.0012,
                min_value=2.5,
                max_value=4.2,
                calibration_points=[(0, 2.5), (4095, 4.2)]
            ),
            SensorType.SIGNAL: SensorConfig(
                sensor_type=SensorType.SIGNAL,
                gpio_pin=0,
                sampling_rate_hz=0.2,
                calibration_offset=-100,
                calibration_scale=0.05,
                min_value=-100,
                max_value=0,
                calibration_points=[(0, -100), (4095, 0)]
            )
        }
        
        for sensor_type, config in configs.items():
            self.sensors[sensor_type] = SensorDriver(config)
    
    def _register_commands(self):
        self.commands = {
            "reboot": self._cmd_reboot,
            "calibrate": self._cmd_calibrate,
            "set_interval": self._cmd_set_interval,
            "ota_start": self._cmd_ota_start,
            "ota_abort": self._cmd_ota_abort,
            "factory_reset": self._cmd_factory_reset,
            "get_status": self._cmd_get_status,
            "set_config": self._cmd_set_config,
            "run_self_test": self._cmd_self_test,
            "enter_sleep": self._cmd_enter_sleep,
            "wake_up": self._cmd_wake_up
        }
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.mqtt_connected = True
            self.state = ESP32State.RUNNING
            self._publish_status("online")
            client.subscribe(self.command_topic)
            client.subscribe(f"{self.command_topic}/#")
            print(f"[{self.device_id}] MQTT connected")
        else:
            self.state = ESP32State.ERROR
            self._log_error(f"MQTT connection failed: {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False
        self.state = ESP32State.ERROR if rc != 0 else ESP32State.OFFLINE
        self._log_error(f"MQTT disconnected: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic.startswith(self.command_topic):
                cmd = topic.split("/")[-1]
                if cmd in self.commands:
                    asyncio.create_task(self.commands[cmd](payload))
        except Exception as e:
            self._log_error(f"Command processing error: {e}")
    
    def _on_mqtt_publish(self, client, userdata, mid):
        pass
    
    async def connect(self):
        self.state = ESP32State.CONNECTING_WIFI
        await asyncio.sleep(0.5)
        
        self.state = ESP32State.CONNECTING_MQTT
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            await asyncio.sleep(1)
        except Exception as e:
            self.state = ESP32State.ERROR
            self._log_error(f"MQTT connection failed: {e}")
            raise
    
    async def disconnect(self):
        self.publish_telemetry = False
        self.publish_sensors = False
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.state = ESP32State.OFFLINE
    
    def _publish_status(self, status: str):
        payload = {
            "device_id": self.device_id,
            "station_id": self.station_id,
            "status": status,
            "firmware_version": self.firmware_version,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.mqtt_client.publish(f"skyguard/{self.station_id}/{self.device_id}/status", json.dumps(payload))
    
    def _publish_telemetry(self, telemetry: ESP32Telemetry):
        payload = asdict(telemetry)
        payload["timestamp"] = telemetry.timestamp.isoformat()
        self.mqtt_client.publish(self.telemetry_topic, json.dumps(payload), qos=1)
    
    def _publish_sensor_reading(self, reading: SensorReading):
        payload = {
            "device_id": self.device_id,
            "station_id": self.station_id,
            "sensor_type": reading.sensor_type.value,
            "value": reading.value,
            "unit": reading.unit,
            "status": reading.status.value,
            "raw_value": reading.raw_value,
            "calibrated": reading.calibrated,
            "timestamp": reading.timestamp.isoformat()
        }
        self.mqtt_client.publish(
            f"{self.mqtt_topic}/{reading.sensor_type.value}",
            json.dumps(payload),
            qos=1
        )
    
    def _log_error(self, message: str):
        self.error_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "state": self.state.value
        })
        print(f"[{self.device_id}] ERROR: {message}")
    
    async def _run_telemetry_loop(self):
        while self.publish_telemetry:
            try:
                telemetry = ESP32Telemetry(
                    device_id=self.device_id,
                    firmware_version=self.firmware_version,
                    uptime_seconds=int(time.time() - self.boot_time),
                    free_heap=random.randint(150000, 200000),
                    cpu_frequency=240,
                    wifi_rssi=random.randint(-80, -30),
                    wifi_channel=random.randint(1, 13),
                    ip_address=f"192.168.1.{random.randint(10, 200)}",
                    mac_address=":".join([f"{random.randint(0,255):02x}" for _ in range(6)]),
                    temperature=self.sensors[SensorType.TEMPERATURE].last_reading.value if self.sensors[SensorType.TEMPERATURE].last_reading else 25.0,
                    battery_voltage=self.sensors[SensorType.BATTERY].last_reading.value if self.sensors[SensorType.BATTERY].last_reading else 3.7,
                    battery_percentage=random.uniform(20, 100),
                    signal_strength=random.randint(-80, -30),
                    errors_count=sum(s.error_count for s in self.sensors.values()),
                    watchdog_resets=0,
                    brownout_resets=0,
                    timestamp=datetime.utcnow()
                )
                
                self._publish_telemetry(telemetry)
                
            except Exception as e:
                self._log_error(f"Telemetry publish error: {e}")
            
            await asyncio.sleep(self.telemetry_interval)
    
    async def _run_sensor_loop(self):
        while self.publish_sensors:
            try:
                for sensor_type, driver in self.sensors.items():
                    reading = driver.read()
                    self._publish_sensor_reading(reading)
                
            except Exception as e:
                self._log_error(f"Sensor publish error: {e}")
            
            await asyncio.sleep(self.sensor_interval)
    
    async def run(self):
        await self.connect()
        
        telemetry_task = asyncio.create_task(self._run_telemetry_loop())
        sensor_task = asyncio.create_task(self._run_sensor_loop())
        command_task = asyncio.create_task(self._process_commands())
        
        try:
            await asyncio.gather(telemetry_task, sensor_task, command_task)
        except asyncio.CancelledError:
            pass
    
    async def _process_commands(self):
        while True:
            try:
                cmd, payload = await self.command_queue.get()
                if cmd in self.commands:
                    await self.commands[cmd](payload)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log_error(f"Command processing error: {e}")
    
    async def send_command(self, command: str, payload: Dict = None):
        await self.command_queue.put((command, payload or {}))
    
    async def _cmd_reboot(self, payload: Dict):
        self._log_error("Reboot command received")
        await asyncio.sleep(1)
        await self.disconnect()
        await asyncio.sleep(2)
        await self.connect()
    
    async def _cmd_calibrate(self, payload: Dict):
        sensor_type = SensorType(payload.get("sensor_type"))
        points = payload.get("calibration_points", [])
        
        if sensor_type in self.sensors:
            self.sensors[sensor_type].apply_calibration(points)
            self._log_error(f"Calibration applied to {sensor_type.value}: {points}")
    
    async def _cmd_set_interval(self, payload: Dict):
        self.telemetry_interval = payload.get("telemetry_interval", self.telemetry_interval)
        self.sensor_interval = payload.get("sensor_interval", self.sensor_interval)
        self._log_error(f"Intervals updated: telemetry={self.telemetry_interval}s, sensor={self.sensor_interval}s")
    
    async def _cmd_ota_start(self, payload: Dict):
        self.state = ESP32State.OTA_UPDATE
        self.ota_update = {
            "version": payload.get("version", "1.0.0"),
            "url": payload.get("url", ""),
            "checksum": payload.get("checksum", ""),
            "size": payload.get("size", 0),
            "progress": 0,
            "started_at": datetime.utcnow()
        }
        self._log_error(f"OTA update started: {self.ota_update['version']}")
    
    async def _cmd_ota_abort(self, payload: Dict):
        self.ota_update = None
        self.state = ESP32State.RUNNING
        self._log_error("OTA update aborted")
    
    async def _cmd_factory_reset(self, payload: Dict):
        self._log_error("Factory reset initiated")
        for sensor in self.sensors.values():
            sensor.config.calibration_offset = 0.0
            sensor.config.calibration_scale = 1.0
            sensor.config.calibration_points = []
            sensor.calibrated = False
        
        await asyncio.sleep(1)
        await self._cmd_reboot({})
    
    async def _cmd_get_status(self, payload: Dict):
        status = self.get_full_status()
        self.mqtt_client.publish(
            f"skyguard/{self.station_id}/{self.device_id}/status/response",
            json.dumps(status),
            qos=1
        )
    
    async def _cmd_set_config(self, payload: Dict):
        config_type = payload.get("config_type")
        value = payload.get("value")
        
        if config_type == "telemetry_interval":
            self.telemetry_interval = value
        elif config_type == "sensor_interval":
            self.sensor_interval = value
        elif config_type == "mqtt_topic":
            self.mqtt_topic = value
        
        self._log_error(f"Config updated: {config_type}={value}")
    
    async def _cmd_self_test(self, payload: Dict):
        self._log_error("Self-test initiated")
        
        results = {}
        for sensor_type, driver in self.sensors.items():
            reading = driver.read()
            results[sensor_type.value] = {
                "value": reading.value,
                "status": reading.status.value,
                "calibrated": reading.calibrated
            }
        
        self.mqtt_client.publish(
            f"skyguard/{self.station_id}/{self.device_id}/selftest/response",
            json.dumps({
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "results": results,
                "overall": "PASS" if all(r["status"] == "ok" for r in results.values()) else "FAIL"
            }), qos=1
        )
    
    async def _cmd_enter_sleep(self, payload: Dict):
        duration = payload.get("duration", 300)
        self.state = ESP32State.SLEEPING
        self.publish_telemetry = False
        self.publish_sensors = False
        
        self._log_error(f"Entering deep sleep for {duration}s")
        
        await asyncio.sleep(duration)
        
        await self._cmd_wake_up({})
    
    async def _cmd_wake_up(self, payload: Dict):
        self.state = ESP32State.RUNNING
        self.publish_telemetry = True
        self.publish_sensors = True
        self._log_error("Wake up from sleep")
    
    def get_full_status(self) -> Dict:
        return {
            "device_id": self.device_id,
            "station_id": self.station_id,
            "state": self.state.value,
            "firmware_version": self.firmware_version,
            "hardware_version": self.hardware_version,
            "uptime_seconds": int(time.time() - self.boot_time),
            "mqtt_connected": self.mqtt_connected,
            "telemetry_interval": self.telemetry_interval,
            "sensor_interval": self.sensor_interval,
            "sensors": {
                st.value: {
                    "enabled": self.sensors[st].config.enabled,
                    "calibrated": self.sensors[st].calibrated,
                    "last_reading": asdict(self.sensors[st].last_reading) if self.sensors[st].last_reading else None,
                    "reading_count": self.sensors[st].reading_count,
                    "error_count": self.sensors[st].error_count
                }
                for st in SensorType
            },
            "telemetry": self._get_telemetry()._asdict() if hasattr(self, '_get_telemetry') else {},
            "errors": list(self.error_log)[-10:],
            "mqtt_topic": self.mqtt_topic,
            "command_topic": self.command_topic,
            "telemetry_topic": self.telemetry_topic,
            "free_heap": random.randint(150000, 200000),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def inject_sensor_fault(self, sensor_type: SensorType, fault_type: str, **params):
        driver = self.sensors.get(sensor_type)
        if not driver:
            return
        
        if fault_type == "offset":
            driver.config.calibration_offset += params.get("offset", 5.0)
        elif fault_type == "scale":
            driver.config.calibration_scale *= params.get("scale", 2.0)
        elif fault_type == "noise":
            pass
        elif fault_type == "stuck":
            driver.config.min_value = driver.config.max_value = params.get("value", 25.0)
        elif fault_type == "disconnect":
            driver.config.enabled = False
        
        self._log_error(f"Sensor fault injected: {sensor_type.value} - {fault_type}")
    
    def simulate_battery_drain(self, rate: float = 0.001):
        if SensorType.BATTERY in self.sensors:
            self.sensors[SensorType.BATTERY].config.calibration_offset -= rate
    
    def simulate_wifi_issue(self, rssi: int = -90):
        pass
    
    def get_device_fingerprint(self) -> str:
        data = f"{self.device_id}{self.hardware_version}{self.firmware_version}{self.mac_address}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class ESP32FleetManager:
    def __init__(
        self,
        mqtt_broker: str = "localhost",
        mqtt_port: int = 1883
    ):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.devices: Dict[str, ESP32FirmwareSimulator] = {}
        self.fleet_status = "initializing"
    
    def add_device(self, device_id: str, station_id: str) -> ESP32FirmwareSimulator:
        device = ESP32FirmwareSimulator(
            device_id=device_id,
            station_id=station_id,
            mqtt_broker=self.mqtt_broker,
            mqtt_port=self.mqtt_port
        )
        self.devices[device_id] = device
        return device
    
    async def deploy_fleet(self, station_ids: List[str]):
        self.fleet_status = "deploying"
        
        for i, station_id in enumerate(station_ids):
            device_id = f"ESP32-{i+1:03d}"
            self.add_device(device_id, station_id)
            await self.devices[device_id].connect()
            await asyncio.sleep(0.1)
        
        self.fleet_status = "running"
    
    async def start_all(self):
        tasks = [device.run() for device in self.devices.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self):
        for device in self.devices.values():
            await device.disconnect()
        self.fleet_status = "stopped"
    
    def inject_fleet_fault(self, fault_type: str, device_ids: List[str] = None, **params):
        targets = device_ids or list(self.devices.keys())
        for device_id in targets:
            if device_id in self.devices:
                device = self.devices[device_id]
                if fault_type == "sensor":
                    sensor_type = SensorType(params.get("sensor", "temperature"))
                    device.inject_sensor_fault(sensor_type, params.get("fault", "offset"), **params)
                elif fault_type == "battery":
                    device.simulate_battery_drain(params.get("rate", 0.01))
                elif fault_type == "wifi":
                    device.simulate_wifi_issue(params.get("rssi", -90))
                elif fault_type == "reboot":
                    asyncio.create_task(device._cmd_reboot({}))
    
    def get_fleet_overview(self) -> Dict:
        return {
            "fleet_status": self.fleet_status,
            "total_devices": len(self.devices),
            "online_devices": sum(1 for d in self.devices.values() if d.state == ESP32State.RUNNING),
            "devices": {
                device_id: {
                    "device_id": d.device_id,
                    "station_id": d.station_id,
                    "state": d.state.value,
                    "uptime": int(time.time() - d.boot_time),
                    "mqtt_connected": d.mqtt_connected,
                    "firmware": d.firmware_version,
                    "errors": len(d.error_log)
                }
                for device_id, d in self.devices.items()
            }
        }
    
    def get_aggregated_telemetry(self) -> Dict:
        telemetry_data = []
        for device in self.devices.values():
            if hasattr(device, '_get_telemetry'):
                telemetry_data.append(device._get_telemetry())
        
        if not telemetry_data:
            return {}
        
        return {
            "device_count": len(telemetry_data),
            "avg_battery": np.mean([t.battery_voltage for t in telemetry_data]),
            "avg_temperature": np.mean([t.temperature for t in telemetry_data]),
            "avg_signal": np.mean([t.signal_strength for t in telemetry_data]),
            "total_errors": sum(t.errors_count for t in telemetry_data),
            "timestamp": datetime.utcnow().isoformat()
        }


async def run_fleet_demo():
    fleet = ESP32FleetManager()
    
    stations = ["AWS001", "AWS002", "AWS003", "AWS004", "AWS005", "AWS006", "AWS007", "AWS008"]
    await fleet.deploy_fleet(stations)
    
    print("Fleet deployed. Starting operations...")
    print(fleet.get_fleet_overview())
    
    try:
        await fleet.start_all()
    except KeyboardInterrupt:
        await fleet.stop_all()


if __name__ == "__main__":
    asyncio.run(run_fleet_demo())