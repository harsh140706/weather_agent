"""
weather_processor.py
Normalize and enrich Open-Meteo API responses.

Changes vs original:
  • process() still returns the same flat dict (backward-compatible)
  • process_with_intelligence() returns (flat_dict, WeatherIntelligence)
    — used by app.py when forecast panel or agent output is needed
  • ForecastEngine is lazily instantiated once per WeatherProcessor instance
"""

import logging
from typing import Optional

from forecasting import ForecastEngine
from forecasting.schemas import WeatherIntelligence

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# WMO codes
# ─────────────────────────────────────────────────────────────────────────────

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
    77: ("Snow Grains",          "❄️"),
    80: ("Slight Showers",       "🌦️"),
    81: ("Moderate Showers",     "🌧️"),
    82: ("Violent Showers",      "⛈️"),
    85: ("Snow Showers",         "🌨️"),
    86: ("Heavy Snow Showers",   "❄️"),
    95: ("Thunderstorm",         "⛈️"),
    96: ("Thunderstorm w/ Hail", "⛈️"),
    99: ("Heavy Thunderstorm",   "⛈️"),
}

WIND_DIRECTIONS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def degrees_to_cardinal(degrees: float) -> str:
    if degrees is None:
        return "N/A"
    idx = round(degrees / 22.5) % 16
    return WIND_DIRECTIONS[idx]


def beaufort_scale(wind_kmh: float) -> tuple[int, str]:
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


def sea_state_from_wind(wind_kmh: float) -> str:
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


def marine_risk_level(wind_kmh: float, visibility_m: float, precipitation_mm: float) -> tuple[str, str]:
    score = 0
    if wind_kmh > 50:    score += 3
    elif wind_kmh > 30:  score += 2
    elif wind_kmh > 15:  score += 1
    if visibility_m < 1000:   score += 3
    elif visibility_m < 5000: score += 2
    elif visibility_m < 10000: score += 1
    if precipitation_mm > 5:  score += 2
    elif precipitation_mm > 1: score += 1
    if score >= 6: return "CRITICAL", "#FF2D2D"
    if score >= 4: return "HIGH",     "#FF8C00"
    if score >= 2: return "MODERATE", "#FFD700"
    return "LOW",     "#00C851"


# ─────────────────────────────────────────────────────────────────────────────

class WeatherProcessor:
    """
    Processes raw Open-Meteo responses into enriched display-ready structures.

    process()                 → flat dict  (backward-compatible, used by UI)
    process_with_intelligence() → (flat dict, WeatherIntelligence)
    """

    def __init__(self):
        self._engine: Optional[ForecastEngine] = None

    @property
    def engine(self) -> ForecastEngine:
        if self._engine is None:
            self._engine = ForecastEngine()
        return self._engine

    # ── Backward-compatible flat dict output ─────────────────────────────────

    def process(self, raw: dict, vessel_name: str = "Unknown") -> Optional[dict]:
        """Returns the same flat dict as before — no breaking changes."""
        if not raw or "current" not in raw:
            return None
        return self._build_flat(raw, vessel_name)

    # ── New: enriched output with predictive intelligence ─────────────────────

    def process_with_intelligence(
        self,
        raw: dict,
        vessel_name: str = "Unknown",
        mmsi: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> tuple[Optional[dict], Optional[WeatherIntelligence]]:
        """
        Returns (flat_dict, WeatherIntelligence).
        flat_dict is passed to existing UI components unchanged.
        WeatherIntelligence is passed to new forecast UI and available for
        agent-to-agent consumption via .to_dict() / .to_json().
        """
        flat = self.process(raw, vessel_name)
        if flat is None:
            return None, None

        intelligence = self.engine.build(
            flat,
            vessel_name=vessel_name,
            mmsi=mmsi,
            latitude=latitude,
            longitude=longitude,
        )
        return flat, intelligence

    # ── Internal builder ──────────────────────────────────────────────────────

    def _build_flat(self, raw: dict, vessel_name: str) -> dict:
        cur = raw.get("current", {})

        temp       = cur.get("temperature_2m")
        feels_like = cur.get("apparent_temperature")
        humidity   = cur.get("relative_humidity_2m")
        wind_speed = cur.get("wind_speed_10m")
        wind_dir   = cur.get("wind_direction_10m")
        pressure   = cur.get("surface_pressure")
        precip     = cur.get("precipitation", 0) or 0
        cloud      = cur.get("cloud_cover")
        visibility = cur.get("visibility", 10000) or 10000
        gusts      = cur.get("wind_gusts_10m")
        wmo_code   = cur.get("weather_code", 0)

        condition_label, condition_icon = WMO_CODES.get(wmo_code, ("Unknown", "❓"))
        wind_cardinal = degrees_to_cardinal(wind_dir)
        bft_num, bft_desc = beaufort_scale(wind_speed or 0)
        sea_state = sea_state_from_wind(wind_speed or 0)
        risk_label, risk_color = marine_risk_level(wind_speed or 0, visibility, precip)

        return {
            "vessel_name":       vessel_name,
            "timezone":          raw.get("timezone", "UTC"),
            "current_time":      cur.get("time", ""),
            "temperature":       temp,
            "feels_like":        feels_like,
            "humidity":          humidity,
            "wind_speed":        wind_speed,
            "wind_direction":    wind_dir,
            "wind_cardinal":     wind_cardinal,
            "wind_gusts":        gusts,
            "pressure":          pressure,
            "precipitation":     precip,
            "cloud_cover":       cloud,
            "visibility":        visibility,
            "condition":         condition_label,
            "condition_icon":    condition_icon,
            "beaufort_num":      bft_num,
            "beaufort_desc":     bft_desc,
            "sea_state":         sea_state,
            "marine_risk":       risk_label,
            "marine_risk_color": risk_color,
            "hourly":            raw.get("hourly", {}),
            "daily":             raw.get("daily", {}),
            "units": {
                "temperature":   raw.get("current_units", {}).get("temperature_2m", "°C"),
                "wind_speed":    raw.get("current_units", {}).get("wind_speed_10m", "km/h"),
                "pressure":      raw.get("current_units", {}).get("surface_pressure", "hPa"),
                "precipitation": raw.get("current_units", {}).get("precipitation", "mm"),
                "visibility":    raw.get("current_units", {}).get("visibility", "m"),
            },
        }
