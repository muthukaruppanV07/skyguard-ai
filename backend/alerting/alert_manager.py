import asyncio
import smtplib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
import uuid
from pathlib import Path
import json


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


class AlertChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    PUSH = "push"
    TELEGRAM = "telegram"


@dataclass
class Alert:
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str
    station_id: str = ""
    anomaly_id: int = 0
    root_cause: str = ""
    anomaly_score: float = 0.0
    confidence: float = 0.0
    status: AlertStatus = AlertStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: str = ""
    channels: List[AlertChannel] = field(default_factory=list)
    sent_channels: List[AlertChannel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class AlertRule:
    rule_id: str
    name: str
    description: str
    conditions: Dict[str, Any]
    severity: AlertSeverity
    channels: List[AlertChannel]
    cooldown_minutes: int = 15
    enabled: bool = True
    stations: List[str] = field(default_factory=list)
    anomaly_types: List[str] = field(default_factory=list)
    min_score: float = 0.0
    max_alerts_per_hour: int = 10


class NotificationChannel(ABC):
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        pass
    
    @abstractmethod
    def get_channel_type(self) -> AlertChannel:
        pass


class EmailChannel(NotificationChannel):
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_email: str = "",
        to_emails: List[str] = None,
        use_tls: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email or username
        self.to_emails = to_emails or []
        self.use_tls = use_tls
    
    def get_channel_type(self) -> AlertChannel:
        return AlertChannel.EMAIL
    
    async def send(self, alert: Alert) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            
            text_body = self._create_text_body(alert)
            html_body = self._create_html_body(alert)
            
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email, msg)
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False
    
    def _send_email(self, msg: MIMEMultipart):
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(msg)
    
    def _create_text_body(self, alert: Alert) -> str:
        return f"""
SkyGuard AI Alert

Severity: {alert.severity.value.upper()}
Station: {alert.station_id}
Anomaly: {alert.root_cause}
Score: {alert.anomaly_score:.1f}
Confidence: {alert.confidence:.0%}

{alert.message}

Time: {alert.created_at.isoformat()}
Alert ID: {alert.alert_id}
"""
    
    def _create_html_body(self, alert: Alert) -> str:
        severity_colors = {
            AlertSeverity.INFO: "#3b82f6",
            AlertSeverity.WARNING: "#f59e0b",
            AlertSeverity.CRITICAL: "#ef4444",
            AlertSeverity.EMERGENCY: "#7c2d12"
        }
        color = severity_colors.get(alert.severity, "#6b7280")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f3f4f6; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }}
        .header {{ background: {color}; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .field {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #374151; }}
        .value {{ color: #1f2937; }}
        .footer {{ background: #f9fafb; padding: 15px; text-align: center; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SkyGuard AI Alert</h1>
            <p style="margin: 0;">{alert.severity.value.upper()} - {alert.title}</p>
        </div>
        <div class="content">
            <div class="field"><span class="label">Station:</span> <span class="value">{alert.station_id}</span></div>
            <div class="field"><span class="label">Anomaly Type:</span> <span class="value">{alert.root_cause}</span></div>
            <div class="field"><span class="label">Anomaly Score:</span> <span class="value">{alert.anomaly_score:.1f}/100</span></div>
            <div class="field"><span class="label">Confidence:</span> <span class="value">{alert.confidence:.0%}</span></div>
            <div class="field"><span class="label">Severity:</span> <span class="value">{alert.severity.value.upper()}</span></div>
            <div class="field"><span class="label">Message:</span> <span class="value">{alert.message}</span></div>
            <div class="field"><span class="label">Time:</span> <span class="value">{alert.created_at.isoformat()}</span></div>
            <div class="field"><span class="label">Alert ID:</span> <span class="value">{alert.alert_id}</span></div>
        </div>
        <div class="footer">
            SkyGuard AI - AWS Intelligent Anomaly Detection System
        </div>
    </div>
</body>
</html>
"""


class WebhookChannel(NotificationChannel):
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None, timeout: int = 10):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
    
    def get_channel_type(self) -> AlertChannel:
        return AlertChannel.WEBHOOK
    
    async def send(self, alert: Alert) -> bool:
        try:
            payload = {
                "alert_id": alert.alert_id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "station_id": alert.station_id,
                "anomaly_id": alert.anomaly_id,
                "root_cause": alert.root_cause,
                "anomaly_score": alert.anomaly_score,
                "confidence": alert.confidence,
                "timestamp": alert.created_at.isoformat(),
                "metadata": alert.metadata
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers
                ) as response:
                    return response.status < 400
        except Exception as e:
            print(f"Webhook send failed: {e}")
            return False


class SlackChannel(NotificationChannel):
    def __init__(self, webhook_url: str, channel: str = None, username: str = "SkyGuard AI"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
    
    def get_channel_type(self) -> AlertChannel:
        return AlertChannel.SLACK
    
    async def send(self, alert: Alert) -> bool:
        try:
            color_map = {
                AlertSeverity.INFO: "#3b82f6",
                AlertSeverity.WARNING: "#f59e0b",
                AlertSeverity.CRITICAL: "#ef4444",
                AlertSeverity.EMERGENCY: "#7c2d12"
            }
            
            payload = {
                "username": self.username,
                "icon_emoji": ":satellite:",
                "attachments": [{
                    "color": color_map.get(alert.severity, "#6b7280"),
                    "title": f"[{alert.severity.value.upper()}] {alert.title}",
                    "fields": [
                        {"title": "Station", "value": alert.station_id, "short": True},
                        {"title": "Anomaly", "value": alert.root_cause, "short": True},
                        {"title": "Score", "value": f"{alert.anomaly_score:.1f}/100", "short": True},
                        {"title": "Confidence", "value": f"{alert.confidence:.0%}", "short": True},
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Time", "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S"), "short": True}
                    ],
                    "text": alert.message,
                    "footer": "SkyGuard AI",
                    "ts": int(alert.created_at.timestamp())
                }]
            }
            
            if self.channel:
                payload["channel"] = self.channel
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    return response.status < 400
        except Exception as e:
            print(f"Slack send failed: {e}")
            return False


class TelegramChannel(NotificationChannel):
    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def get_channel_type(self) -> AlertChannel:
        return AlertChannel.TELEGRAM
    
    async def send(self, alert: Alert) -> bool:
        try:
            text = (
                f"🚨 <b>SkyGuard AI Alert</b>\n\n"
                f"<b>Severity:</b> {alert.severity.value.upper()}\n"
                f"<b>Station:</b> {alert.station_id}\n"
                f"<b>Anomaly:</b> {alert.root_cause}\n"
                f"<b>Score:</b> {alert.anomaly_score:.1f}/100\n"
                f"<b>Confidence:</b> {alert.confidence:.0%}\n\n"
                f"{alert.message}\n\n"
                f"<i>Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
                f"<i>Alert ID: {alert.alert_id}</i>"
            )
            
            async with aiohttp.ClientSession() as session:
                for chat_id in self.chat_ids:
                    async with session.post(
                        f"{self.base_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": "HTML"
                        }
                    ) as response:
                        if response.status >= 400:
                            return False
            return True
        except Exception as e:
            print(f"Telegram send failed: {e}")
            return False


class AlertManager:
    def __init__(self, config_path: str = "config/alerts.json"):
        self.config_path = Path(config_path)
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, Alert] = {}
        self.channels: Dict[AlertChannel, NotificationChannel] = {}
        self.suppression_cache: Dict[str, datetime] = {}
        self.alert_history: List[Alert] = []
        self.max_history = 10000
        self.handlers: List[Callable] = []
        self.running = False
        self._processing_task = None
        self._queue = asyncio.Queue()
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_config()
    
    def add_channel(self, channel: NotificationChannel):
        self.channels[channel.get_channel_type()] = channel
    
    def add_rule(self, rule: AlertRule):
        self.rules[rule.rule_id] = rule
        self._save_config()
    
    def remove_rule(self, rule_id: str):
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._save_config()
    
    def add_handler(self, handler: Callable[[Alert], Any]):
        self.handlers.append(handler)
    
    async def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        station_id: str = "",
        anomaly_id: int = 0,
        root_cause: str = "",
        anomaly_score: float = 0.0,
        confidence: float = 0.0,
        channels: List[AlertChannel] = None,
        metadata: Dict = None
    ) -> Alert:
        alert = Alert(
            alert_id=str(uuid.uuid4())[:12],
            title=title,
            message=message,
            severity=severity,
            source=source,
            station_id=station_id,
            anomaly_id=anomaly_id,
            root_cause=root_cause,
            anomaly_score=anomaly_score,
            confidence=confidence,
            channels=channels or [AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            metadata=metadata or {}
        )
        
        if self._should_suppress(alert):
            alert.status = AlertStatus.SUPPRESSED
            return alert
        
        self.alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        await self._queue.put(alert)
        return alert
    
    def _should_suppress(self, alert: Alert) -> bool:
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if rule.stations and alert.station_id not in rule.stations:
                continue
            
            if rule.anomaly_types and alert.root_cause not in rule.anomaly_types:
                continue
            
            if alert.anomaly_score < rule.min_score:
                continue
            
            key = f"{rule.rule_id}:{alert.station_id}:{alert.root_cause}"
            if key in self.suppression_cache:
                last_sent = self.suppression_cache[key]
                if datetime.utcnow() - last_sent < timedelta(minutes=rule.cooldown_minutes):
                    return True
        
        return False
    
    async def _process_queue(self):
        self.running = True
        while self.running:
            try:
                alert = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_alert(alert)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing alert queue: {e}")
    
    async def _process_alert(self, alert: Alert):
        alert.status = AlertStatus.SENT
        
        for channel_type in alert.channels:
            if channel_type in self.channels:
                try:
                    channel = self.channels[channel_type]
                    success = await channel.send(alert)
                    if success:
                        alert.sent_channels.append(channel_type)
                    else:
                        alert.retry_count += 1
                except Exception as e:
                    print(f"Channel {channel_type} send failed: {e}")
                    alert.retry_count += 1
        
        if alert.sent_channels:
            alert.status = AlertStatus.SENT
            for rule in self.rules.values():
                if rule.enabled and self._rule_matches(rule, alert):
                    key = f"{rule.rule_id}:{alert.station_id}:{alert.root_cause}"
                    self.suppression_cache[key] = datetime.utcnow()
        else:
            alert.status = AlertStatus.FAILED
        
        for handler in self.handlers:
            try:
                await handler(alert)
            except Exception as e:
                print(f"Handler error: {e}")
    
    def _rule_matches(self, rule: AlertRule, alert: Alert) -> bool:
        if rule.stations and alert.station_id not in rule.stations:
            return False
        if rule.anomaly_types and alert.root_cause not in rule.anomaly_types:
            return False
        if alert.anomaly_score < rule.min_score:
            return False
        return True
    
    async def start(self):
        self.running = True
        self._processing_task = asyncio.create_task(self._process_queue())
    
    async def stop(self):
        self.running = False
        if self._processing_task:
            self._processing_task.cancel()
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            return True
        return False
    
    async def resolve_alert(self, alert_id: str) -> bool:
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            return True
        return False
    
    def get_alerts(
        self,
        status: AlertStatus = None,
        station_id: str = None,
        severity: AlertSeverity = None,
        limit: int = 100
    ) -> List[Alert]:
        alerts = list(self.alerts.values())
        
        if status:
            alerts = [a for a in alerts if a.status == status]
        if station_id:
            alerts = [a for a in alerts if a.station_id == station_id]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        alerts.sort(key=lambda x: x.created_at, reverse=True)
        return alerts[:limit]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        total = len(self.alerts)
        by_status = defaultdict(int)
        by_severity = defaultdict(int)
        by_station = defaultdict(int)
        
        for alert in self.alerts.values():
            by_status[alert.status.value] += 1
            by_severity[alert.severity.value] += 1
            if alert.station_id:
                by_station[alert.station_id] += 1
        
        return {
            "total_alerts": total,
            "by_status": dict(by_status),
            "by_severity": dict(by_severity),
            "by_station": dict(by_station),
            "pending": by_status.get("pending", 0),
            "unacknowledged": sum(
                v for k, v in by_status.items() 
                if k in ["pending", "sent"]
            )
        }
    
    def _save_config(self):
        config = {
            "rules": {k: asdict(v) for k, v in self.rules.items()}
        }
        self.config_path.write_text(json.dumps(config, default=str))
    
    def _load_config(self):
        if self.config_path.exists():
            try:
                config = json.loads(self.config_path.read_text())
                for rule_id, rule_data in config.get("rules", {}).items():
                    rule_data["severity"] = AlertSeverity(rule_data["severity"])
                    rule_data["channels"] = [AlertChannel(c) for c in rule_data["channels"]]
                    self.rules[rule_id] = AlertRule(**rule_data)
            except Exception as e:
                print(f"Failed to load alert config: {e}")


class AlertRuleBuilder:
    def __init__(self, manager: AlertManager):
        self.manager = manager
        self.rule_id = str(uuid.uuid4())[:12]
        self.name = ""
        self.description = ""
        self.conditions = {}
        self.severity = AlertSeverity.WARNING
        self.channels = [AlertChannel.EMAIL]
        self.cooldown_minutes = 15
        self.stations = []
        self.anomaly_types = []
        self.min_score = 0.0
        self.max_alerts_per_hour = 10
    
    def with_name(self, name: str):
        self.name = name
        return self
    
    def with_description(self, desc: str):
        self.description = desc
        return self
    
    def with_severity(self, severity: AlertSeverity):
        self.severity = severity
        return self
    
    def with_channels(self, channels: List[AlertChannel]):
        self.channels = channels
        return self
    
    def with_cooldown(self, minutes: int):
        self.cooldown_minutes = minutes
        return self
    
    def for_stations(self, stations: List[str]):
        self.stations = stations
        return self
    
    def for_anomaly_types(self, types: List[str]):
        self.anomaly_types = types
        return self
    
    def with_min_score(self, score: float):
        self.min_score = score
        return self
    
    def with_condition(self, key: str, value: Any):
        self.conditions[key] = value
        return self
    
    def build(self) -> AlertRule:
        rule = AlertRule(
            rule_id=self.rule_id,
            name=self.name,
            description=self.description,
            conditions=self.conditions,
            severity=self.severity,
            channels=self.channels,
            cooldown_minutes=self.cooldown_minutes,
            stations=self.stations,
            anomaly_types=self.anomaly_types,
            min_score=self.min_score,
            max_alerts_per_hour=self.max_alerts_per_hour
        )
        self.manager.add_rule(rule)
        return rule


def create_alert_manager(config_path: str = "config/alerts.json") -> AlertManager:
    return AlertManager(config_path)


def create_default_alert_manager() -> AlertManager:
    manager = AlertManager()
    
    manager.add_rule(AlertRule(
        rule_id="critical_anomaly",
        name="Critical Anomaly Detection",
        description="Alert on critical severity anomalies",
        conditions={"severity": "critical"},
        severity=AlertSeverity.CRITICAL,
        channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK],
        cooldown_minutes=5,
        min_score=85
    ))
    
    manager.add_rule(AlertRule(
        rule_id="high_anomaly",
        name="High Anomaly Detection",
        description="Alert on high severity anomalies",
        conditions={"severity": "high"},
        severity=AlertSeverity.WARNING,
        channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
        cooldown_minutes=15,
        min_score=70
    ))
    
    manager.add_rule(AlertRule(
        rule_id="sensor_drift",
        name="Sensor Drift Detection",
        description="Alert on sensor calibration drift",
        conditions={"root_cause": "SENSOR_DRIFT"},
        severity=AlertSeverity.WARNING,
        channels=[AlertChannel.EMAIL],
        cooldown_minutes=60,
        anomaly_types=["SENSOR_DRIFT"]
    ))
    
    manager.add_rule(AlertRule(
        rule_id="frozen_sensor",
        name="Frozen Sensor Detection",
        description="Alert on frozen/stuck sensor readings",
        conditions={"root_cause": "FROZEN_SENSOR"},
        severity=AlertSeverity.HIGH,
        channels=[AlertChannel.EMAIL, AlertChannel.SMS],
        cooldown_minutes=30,
        anomaly_types=["FROZEN_SENSOR"]
    ))
    
    manager.add_rule(AlertRule(
        rule_id="esp32_battery_low",
        name="ESP32 Battery Low",
        description="Alert on ESP32 device battery depletion",
        conditions={"source": "esp32", "type": "battery_low"},
        severity=AlertSeverity.WARNING,
        channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
        cooldown_minutes=60
    ))
    
    return manager