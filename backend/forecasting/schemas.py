"""
schemas.py
Typed weather intelligence schemas for multi-agent interoperability.

These dataclasses serve as the canonical data contract between the Weather Agent
and downstream consumers (Navigation Agent, Risk Agent, Route Planner, etc.).
Designed to be serializable to JSON for REST/MCP/LangGraph agent communication.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class AlertLevel(str, Enum):
    NONE     = "NONE"
    ADVISORY = "ADVISORY"
    WATCH    = "WATCH"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


class MarineRisk(str, Enum):
    LOW      = "LOW"
    MODERATE = "MODERATE"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class ForecastConfidence(str, Enum):
    HIGH   = "HIGH"    # 0–2 days:  ≥80% confidence
    MEDIUM = "MEDIUM"  # 3–4 days:  50–80%
    LOW    = "LOW"     # 5–7 days:  <50%


class SeaState(str, Enum):
    GLASSY       = "Glassy"
    RIPPLED      = "Rippled"
    WAVELETS     = "Wavelets"
    SLIGHT       = "Slight"
    MODERATE     = "Moderate"
    ROUGH        = "Rough"
    VERY_ROUGH   = "Very Rough"
    HIGH         = "High"
    VERY_HIGH    = "Very High"
    PHENOMENAL   = "Phenomenal"


# ─────────────────────────────────────────────────────────────────────────────
# Per-day forecast
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DayForecast:
    """Single-day enriched forecast with predictive features."""
    date: str                               # ISO date YYYY-MM-DD
    day_label: str                          # "Today", "Tomorrow", "Wed", …

    # Raw API values
    temp_max: float
    temp_min: float
    wind_max: float                         # km/h
    wind_dominant_dir: float                # degrees
    precipitation_sum: float                # mm
    weather_code: int

    # Derived / enriched
    condition: str
    condition_icon: str
    beaufort_num: int
    beaufort_desc: str
    sea_state: str
    marine_risk: MarineRisk
    marine_risk_color: str
    marine_risk_score: int                  # 0–10 numeric severity

    # Predictive
    confidence: ForecastConfidence
    confidence_pct: float                   # 0.0–1.0
    wind_trend: str                         # "rising", "falling", "stable"
    temp_trend: str
    precip_trend: str
    alert_level: AlertLevel
    alert_messages: list[str] = field(default_factory=list)

    # Smoothed values (rolling average)
    wind_smoothed: float = 0.0
    precip_smoothed: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["marine_risk"] = self.marine_risk.value
        d["confidence"]  = self.confidence.value
        d["alert_level"] = self.alert_level.value
        return d


# ─────────────────────────────────────────────────────────────────────────────
# Severe weather event
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeatherAlert:
    """Detected severe weather event or anomaly."""
    day_index: int                          # 0 = today, 6 = day+6
    date: str
    alert_level: AlertLevel
    category: str                           # "wind", "precipitation", "transition", "visibility"
    message: str
    metric_value: float
    threshold: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["alert_level"] = self.alert_level.value
        return d


# ─────────────────────────────────────────────────────────────────────────────
# Top-level intelligence object (agent output schema)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeatherIntelligence:
    """
    Canonical output of the Weather Agent.

    Consumed by: Navigation Agent, Risk Agent, Route Planner, Safety Agent.
    Serializable to JSON for REST/MCP/LangGraph communication.
    """
    # Identity
    vessel_name: str
    mmsi: str
    latitude: float
    longitude: float
    generated_at: str                       # ISO datetime UTC

    # Current conditions (pass-through from WeatherProcessor)
    current: dict

    # 7-day enriched forecast
    forecast: list[DayForecast] = field(default_factory=list)

    # Aggregate intelligence
    overall_alert_level: AlertLevel = AlertLevel.NONE
    alerts: list[WeatherAlert] = field(default_factory=list)
    worst_day_index: int = 0                # index into forecast[]
    worst_marine_risk: MarineRisk = MarineRisk.LOW
    avg_confidence: float = 1.0             # 0.0–1.0
    anomaly_detected: bool = False
    anomaly_description: str = ""

    # Trend summaries (for route planners)
    wind_7day_trend: str = "stable"
    precip_7day_trend: str = "stable"

    # Agent metadata
    schema_version: str = "1.0"
    agent_id: str = "weather_agent_v1"

    def to_dict(self) -> dict:
        return {
            "vessel_name":        self.vessel_name,
            "mmsi":               self.mmsi,
            "latitude":           self.latitude,
            "longitude":          self.longitude,
            "generated_at":       self.generated_at,
            "current":            self.current,
            "forecast":           [d.to_dict() for d in self.forecast],
            "overall_alert_level":self.overall_alert_level.value,
            "alerts":             [a.to_dict() for a in self.alerts],
            "worst_day_index":    self.worst_day_index,
            "worst_marine_risk":  self.worst_marine_risk.value,
            "avg_confidence":     round(self.avg_confidence, 3),
            "anomaly_detected":   self.anomaly_detected,
            "anomaly_description":self.anomaly_description,
            "wind_7day_trend":    self.wind_7day_trend,
            "precip_7day_trend":  self.precip_7day_trend,
            "schema_version":     self.schema_version,
            "agent_id":           self.agent_id,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
