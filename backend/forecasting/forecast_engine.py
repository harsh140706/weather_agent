"""
forecast_engine.py
Maritime Weather Forecast Engine — predictive modeling layer.

Responsibilities:
  1. Trend estimation (linear regression on 7-day wind / precip / temp arrays)
  2. Rolling-average smoothing to reduce noise
  3. Confidence decay — uncertainty grows with forecast horizon
  4. Anomaly detection — sudden transitions, outliers via IQR + gradient check
  5. Severe-weather alerts — per-day threshold evaluation
  6. Marine risk scoring — composite numeric score per day
  7. Output: WeatherIntelligence typed object ready for agent consumption

This class is intentionally pure-Python / numpy-only (no Streamlit, no HTTP).
It can be unit-tested, imported by a FastAPI microservice, or called from within
a LangGraph / CrewAI tool wrapper with zero modification.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from .schemas import (
    WeatherIntelligence,
    DayForecast,
    WeatherAlert,
    AlertLevel,
    MarineRisk,
    ForecastConfidence,
)

# Re-export WMO lookup from processor to avoid circular imports
WMO_CODES: dict[int, tuple[str, str]] = {
    0:  ("Clear Sky",            "☀️"),
    1:  ("Mainly Clear",         "🌤️"),
    2:  ("Partly Cloudy",        "⛅"),
    3:  ("Overcast",             "☁️"),
    45: ("Foggy",                "🌫️"),
    48: ("Icy Fog",              "🌫️"),
    51: ("Light Drizzle",        "🌦️"),
    53: ("Moderate Drizzle",     "🌦️"),
    55: ("Dense Drizzle",        "🌧️"),
    61: ("Slight Rain",          "🌧️"),
    63: ("Moderate Rain",        "🌧️"),
    65: ("Heavy Rain",           "🌧️"),
    71: ("Slight Snow",          "🌨️"),
    73: ("Moderate Snow",        "🌨️"),
    75: ("Heavy Snow",           "❄️"),
    80: ("Slight Showers",       "🌦️"),
    81: ("Moderate Showers",     "🌧️"),
    82: ("Violent Showers",      "⛈️"),
    95: ("Thunderstorm",         "⛈️"),
    96: ("Thunderstorm w/ Hail", "⛈️"),
    99: ("Heavy Thunderstorm",   "⛈️"),
}

RISK_COLORS: dict[MarineRisk, str] = {
    MarineRisk.LOW:      "#00C851",
    MarineRisk.MODERATE: "#FFD700",
    MarineRisk.HIGH:     "#FF8C00",
    MarineRisk.CRITICAL: "#FF2D2D",
}

# Confidence decay: day 0 = 95%, day 6 = 45%
_CONFIDENCE_CURVE = [0.95, 0.88, 0.80, 0.70, 0.60, 0.52, 0.45]

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Pure helper functions (stateless, testable)
# ─────────────────────────────────────────────────────────────────────────────

def _beaufort(wind_kmh: float) -> tuple[int, str]:
    thresholds = [
        (1, 0, "Calm"), (6, 1, "Light Air"), (12, 2, "Light Breeze"),
        (20, 3, "Gentle Breeze"), (29, 4, "Moderate Breeze"),
        (39, 5, "Fresh Breeze"), (50, 6, "Strong Breeze"),
        (62, 7, "High Wind"), (75, 8, "Gale"), (89, 9, "Strong Gale"),
        (103, 10, "Storm"), (117, 11, "Violent Storm"),
        (float("inf"), 12, "Hurricane"),
    ]
    for limit, bft, desc in thresholds:
        if wind_kmh < limit:
            return bft, desc
    return 12, "Hurricane"


def _sea_state(wind_kmh: float) -> str:
    if wind_kmh < 1:   return "Glassy"
    if wind_kmh < 6:   return "Rippled"
    if wind_kmh < 12:  return "Wavelets"
    if wind_kmh < 20:  return "Slight"
    if wind_kmh < 29:  return "Moderate"
    if wind_kmh < 39:  return "Rough"
    if wind_kmh < 50:  return "Very Rough"
    if wind_kmh < 62:  return "High"
    if wind_kmh < 75:  return "Very High"
    return "Phenomenal"


def _marine_risk_score(wind_kmh: float, precip_mm: float) -> int:
    """
    Composite marine risk score 0–10.
    Incorporates wind severity (Beaufort-weighted) and precipitation intensity.
    """
    # Wind component: 0–7 points
    wind_score = 0
    if wind_kmh >= 117: wind_score = 7
    elif wind_kmh >= 89: wind_score = 6
    elif wind_kmh >= 75: wind_score = 5
    elif wind_kmh >= 62: wind_score = 4
    elif wind_kmh >= 50: wind_score = 3
    elif wind_kmh >= 29: wind_score = 2
    elif wind_kmh >= 15: wind_score = 1

    # Precipitation component: 0–3 points
    precip_score = 0
    if precip_mm >= 20:  precip_score = 3
    elif precip_mm >= 8:  precip_score = 2
    elif precip_mm >= 2:  precip_score = 1

    return min(wind_score + precip_score, 10)


def _score_to_risk(score: int) -> tuple[MarineRisk, str]:
    if score >= 7: return MarineRisk.CRITICAL, RISK_COLORS[MarineRisk.CRITICAL]
    if score >= 5: return MarineRisk.HIGH,     RISK_COLORS[MarineRisk.HIGH]
    if score >= 3: return MarineRisk.MODERATE, RISK_COLORS[MarineRisk.MODERATE]
    return MarineRisk.LOW, RISK_COLORS[MarineRisk.LOW]


def _confidence_for_day(day_idx: int) -> tuple[ForecastConfidence, float]:
    pct = _CONFIDENCE_CURVE[min(day_idx, 6)]
    if pct >= 0.80: level = ForecastConfidence.HIGH
    elif pct >= 0.55: level = ForecastConfidence.MEDIUM
    else: level = ForecastConfidence.LOW
    return level, pct


def _rolling_smooth(arr: np.ndarray, window: int = 3) -> np.ndarray:
    """Simple centred rolling mean — edges use smaller windows (no NaN output)."""
    out = np.empty_like(arr, dtype=float)
    n = len(arr)
    for i in range(n):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        out[i] = float(np.mean(arr[lo:hi]))
    return out


def _linear_trend(arr: np.ndarray) -> str:
    """
    Fit a 1-D linear regression.
    Returns 'rising', 'falling', or 'stable' based on slope magnitude.
    """
    if len(arr) < 2:
        return "stable"
    x = np.arange(len(arr), dtype=float)
    # Use numpy polyfit (degree 1)
    slope = np.polyfit(x, arr.astype(float), 1)[0]
    # Relative threshold: 2% of mean per day
    mean_val = float(np.mean(np.abs(arr))) or 1.0
    rel_slope = slope / mean_val
    if rel_slope >  0.02: return "rising"
    if rel_slope < -0.02: return "falling"
    return "stable"


def _detect_anomalies(
    arr: np.ndarray,
    dates: list[str],
    metric_name: str,
    threshold_multiplier: float = 2.0,
    gradient_threshold: float = 0.4,
) -> list[dict]:
    """
    Detect two kinds of anomalies:
    1. Outliers: values > mean + threshold_multiplier * std  (IQR guard)
    2. Sharp transitions: day-over-day gradient > gradient_threshold * value
    Returns list of anomaly dicts.
    """
    anomalies = []
    if len(arr) < 3:
        return anomalies

    arr_f = arr.astype(float)
    mean = float(np.mean(arr_f))
    std  = float(np.std(arr_f))

    for i, val in enumerate(arr_f):
        # Outlier check
        if std > 0 and abs(val - mean) > threshold_multiplier * std:
            anomalies.append({
                "day_index": i,
                "date": dates[i] if i < len(dates) else "",
                "type": "outlier",
                "metric": metric_name,
                "value": float(val),
                "mean": round(mean, 2),
                "deviation_sigma": round(abs(val - mean) / std, 2),
            })

        # Gradient (sharp transition) check
        if i > 0:
            prev = arr_f[i - 1]
            base = max(abs(prev), 1.0)
            change = abs(val - prev) / base
            if change > gradient_threshold:
                anomalies.append({
                    "day_index": i,
                    "date": dates[i] if i < len(dates) else "",
                    "type": "sharp_transition",
                    "metric": metric_name,
                    "value": float(val),
                    "prev_value": float(prev),
                    "change_pct": round(change * 100, 1),
                })

    return anomalies


def _day_label(date_str: str, idx: int) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if idx == 0: return "Today"
        if idx == 1: return "Tomorrow"
        return dt.strftime("%a")
    except Exception:
        return f"Day {idx}"


# ─────────────────────────────────────────────────────────────────────────────
# Alert evaluation
# ─────────────────────────────────────────────────────────────────────────────

_WIND_ALERT_THRESHOLDS = [
    (117, AlertLevel.CRITICAL, "Hurricane-force winds"),
    (89,  AlertLevel.WARNING,  "Storm-force winds (Bft 10+)"),
    (62,  AlertLevel.WATCH,    "Gale-force winds (Bft 8+)"),
    (39,  AlertLevel.ADVISORY, "Strong winds (Bft 5+)"),
]

_PRECIP_ALERT_THRESHOLDS = [
    (30, AlertLevel.CRITICAL, "Extreme rainfall"),
    (15, AlertLevel.WARNING,  "Heavy rainfall"),
    (8,  AlertLevel.WATCH,    "Moderate rainfall"),
]


def _evaluate_day_alerts(
    day_idx: int,
    date: str,
    wind_max: float,
    precip_sum: float,
    wind_smoothed: float,
    anomalies: list[dict],
) -> tuple[AlertLevel, list[str], list[WeatherAlert]]:
    """Evaluate all alert rules for a single forecast day."""
    messages: list[str] = []
    alert_objects: list[WeatherAlert] = []
    highest = AlertLevel.NONE

    def _bump(lvl: AlertLevel) -> None:
        nonlocal highest
        order = list(AlertLevel)
        if order.index(lvl) > order.index(highest):
            highest = lvl

    # Wind alerts
    for threshold, level, msg in _WIND_ALERT_THRESHOLDS:
        if wind_max >= threshold:
            messages.append(f"⚠️ {msg}: {wind_max:.0f} km/h")
            alert_objects.append(WeatherAlert(
                day_index=day_idx, date=date, alert_level=level,
                category="wind", message=msg,
                metric_value=wind_max, threshold=float(threshold),
            ))
            _bump(level)
            break  # Only highest threshold

    # Precipitation alerts
    for threshold, level, msg in _PRECIP_ALERT_THRESHOLDS:
        if precip_sum >= threshold:
            messages.append(f"🌧️ {msg}: {precip_sum:.1f} mm")
            alert_objects.append(WeatherAlert(
                day_index=day_idx, date=date, alert_level=level,
                category="precipitation", message=msg,
                metric_value=precip_sum, threshold=float(threshold),
            ))
            _bump(level)
            break

    # Anomaly-driven transition alerts
    for anomaly in anomalies:
        if anomaly["day_index"] == day_idx and anomaly["type"] == "sharp_transition":
            metric = anomaly["metric"]
            chg = anomaly["change_pct"]
            msg = f"Rapid {metric} change: {chg:.0f}% in 24h"
            messages.append(f"🔁 {msg}")
            alert_objects.append(WeatherAlert(
                day_index=day_idx, date=date, alert_level=AlertLevel.WATCH,
                category="transition", message=msg,
                metric_value=anomaly["value"], threshold=anomaly["prev_value"],
            ))
            _bump(AlertLevel.WATCH)

    return highest, messages, alert_objects


# ─────────────────────────────────────────────────────────────────────────────
# Main engine
# ─────────────────────────────────────────────────────────────────────────────

class ForecastEngine:
    """
    Stateless forecasting engine.

    Usage:
        engine = ForecastEngine()
        intelligence = engine.build(processed_weather, vessel_info)

    The returned WeatherIntelligence object is the canonical agent output.
    It can be serialized via .to_dict() / .to_json() for inter-agent comms.
    """

    def __init__(self, smoothing_window: int = 3):
        self.smoothing_window = smoothing_window

    # ── Public API ───────────────────────────────────────────────────────────

    def build(
        self,
        processed: dict,
        vessel_name: str = "Unknown",
        mmsi: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> Optional[WeatherIntelligence]:
        """
        Build a full WeatherIntelligence object from a processed weather dict.

        Args:
            processed:    Output of WeatherProcessor.process()
            vessel_name:  Vessel display name
            mmsi:         AIS MMSI string
            latitude:     Decimal latitude
            longitude:    Decimal longitude

        Returns:
            WeatherIntelligence or None if daily data is missing.
        """
        daily = processed.get("daily", {})
        if not daily or "time" not in daily:
            logger.warning("[ForecastEngine] No daily data — cannot build intelligence")
            return None

        try:
            return self._build_intelligence(processed, vessel_name, mmsi, latitude, longitude)
        except Exception as e:
            logger.error(f"[ForecastEngine] build() failed: {e}", exc_info=True)
            return None

    # ── Internal pipeline ────────────────────────────────────────────────────

    def _build_intelligence(
        self,
        processed: dict,
        vessel_name: str,
        mmsi: str,
        lat: float,
        lon: float,
    ) -> WeatherIntelligence:

        daily  = processed.get("daily",  {})
        dates  = daily.get("time", [])
        n_days = len(dates)

        # Extract raw arrays (guard for missing keys)
        wind_arr   = np.array(daily.get("wind_speed_10m_max",          [0.0] * n_days), dtype=float)
        precip_arr = np.array(daily.get("precipitation_sum",           [0.0] * n_days), dtype=float)
        temp_max   = np.array(daily.get("temperature_2m_max",          [0.0] * n_days), dtype=float)
        temp_min   = np.array(daily.get("temperature_2m_min",          [0.0] * n_days), dtype=float)
        wind_dir   = np.array(daily.get("wind_direction_10m_dominant", [0.0] * n_days), dtype=float)
        wmo_codes  = daily.get("weather_code", [0] * n_days)

        # Replace NaN/None
        wind_arr   = np.nan_to_num(wind_arr,   nan=0.0)
        precip_arr = np.nan_to_num(precip_arr, nan=0.0)
        temp_max   = np.nan_to_num(temp_max,   nan=20.0)
        temp_min   = np.nan_to_num(temp_min,   nan=15.0)
        wind_dir   = np.nan_to_num(wind_dir,   nan=0.0)

        # ── Smoothing ──────────────────────────────────────────────────────
        wind_smooth   = _rolling_smooth(wind_arr,   self.smoothing_window)
        precip_smooth = _rolling_smooth(precip_arr, self.smoothing_window)

        # ── Trend estimation ───────────────────────────────────────────────
        wind_trend   = _linear_trend(wind_arr)
        precip_trend = _linear_trend(precip_arr)
        temp_trend   = _linear_trend((temp_max + temp_min) / 2)

        # ── Anomaly detection ──────────────────────────────────────────────
        all_anomalies: list[dict] = []
        all_anomalies += _detect_anomalies(wind_arr,   dates, "wind")
        all_anomalies += _detect_anomalies(precip_arr, dates, "precipitation",
                                            gradient_threshold=0.6)

        # ── Per-day forecast objects ───────────────────────────────────────
        forecast_days: list[DayForecast] = []
        all_alerts:    list[WeatherAlert] = []

        for i in range(n_days):
            date     = dates[i]
            wmax     = float(wind_arr[i])
            psum     = float(precip_arr[i])
            w_smooth = float(wind_smooth[i])
            p_smooth = float(precip_smooth[i])

            wmo  = int(wmo_codes[i]) if i < len(wmo_codes) else 0
            cond_label, cond_icon = WMO_CODES.get(wmo, ("Unknown", "❓"))

            bft_num, bft_desc = _beaufort(wmax)
            sea     = _sea_state(wmax)
            score   = _marine_risk_score(wmax, psum)
            risk, risk_color = _score_to_risk(score)
            conf_lvl, conf_pct = _confidence_for_day(i)

            day_wind_trend   = _linear_trend(wind_arr[max(0, i-2):i+2]) if n_days > 2 else "stable"
            day_temp_trend   = _linear_trend(((temp_max + temp_min) / 2)[max(0, i-2):i+2]) if n_days > 2 else "stable"
            day_precip_trend = _linear_trend(precip_arr[max(0, i-2):i+2]) if n_days > 2 else "stable"

            alert_lvl, alert_msgs, day_alerts = _evaluate_day_alerts(
                i, date, wmax, psum, w_smooth, all_anomalies
            )
            all_alerts.extend(day_alerts)

            forecast_days.append(DayForecast(
                date=date,
                day_label=_day_label(date, i),
                temp_max=float(temp_max[i]),
                temp_min=float(temp_min[i]),
                wind_max=wmax,
                wind_dominant_dir=float(wind_dir[i]),
                precipitation_sum=psum,
                weather_code=wmo,
                condition=cond_label,
                condition_icon=cond_icon,
                beaufort_num=bft_num,
                beaufort_desc=bft_desc,
                sea_state=sea,
                marine_risk=risk,
                marine_risk_color=risk_color,
                marine_risk_score=score,
                confidence=conf_lvl,
                confidence_pct=conf_pct,
                wind_trend=day_wind_trend,
                temp_trend=day_temp_trend,
                precip_trend=day_precip_trend,
                alert_level=alert_lvl,
                alert_messages=alert_msgs,
                wind_smoothed=round(w_smooth, 2),
                precip_smoothed=round(p_smooth, 2),
            ))

        # ── Aggregate intelligence ─────────────────────────────────────────
        alert_order = list(AlertLevel)
        overall_alert = AlertLevel.NONE
        for a in all_alerts:
            if alert_order.index(a.alert_level) > alert_order.index(overall_alert):
                overall_alert = a.alert_level

        risk_order = list(MarineRisk)
        worst_idx  = int(np.argmax([d.marine_risk_score for d in forecast_days]))
        worst_risk = forecast_days[worst_idx].marine_risk if forecast_days else MarineRisk.LOW

        avg_conf = float(np.mean([d.confidence_pct for d in forecast_days])) if forecast_days else 1.0

        anomaly_detected = bool(all_anomalies)
        anomaly_desc = ""
        if all_anomalies:
            # Summarise the most significant anomaly
            a = max(all_anomalies, key=lambda x: x.get("deviation_sigma", x.get("change_pct", 0) / 100))
            if a["type"] == "outlier":
                anomaly_desc = (
                    f"Unusual {a['metric']} on {a.get('date','')} "
                    f"({a['value']:.1f}, {a['deviation_sigma']:.1f}σ above mean)"
                )
            else:
                anomaly_desc = (
                    f"Sharp {a['metric']} transition on {a.get('date','')} "
                    f"({a['change_pct']:.0f}% change in 24h)"
                )

        return WeatherIntelligence(
            vessel_name=vessel_name,
            mmsi=mmsi,
            latitude=lat,
            longitude=lon,
            generated_at=datetime.now(timezone.utc).isoformat(),
            current=processed,
            forecast=forecast_days,
            overall_alert_level=overall_alert,
            alerts=all_alerts,
            worst_day_index=worst_idx,
            worst_marine_risk=worst_risk,
            avg_confidence=round(avg_conf, 3),
            anomaly_detected=anomaly_detected,
            anomaly_description=anomaly_desc,
            wind_7day_trend=wind_trend,
            precip_7day_trend=precip_trend,
        )
