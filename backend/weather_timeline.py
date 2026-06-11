"""
weather_timeline.py
Historical and forecast timeline manager for weather data.
"""

from typing import Optional
import pandas as pd


class WeatherTimeline:
    """
    Slices hourly and daily arrays from a processed weather dict
    into timeline views: Current, 24 Hours, 7 Days.
    """

    def __init__(self, processed_weather: dict):
        self.weather = processed_weather
        self.hourly  = processed_weather.get("hourly", {})
        self.daily   = processed_weather.get("daily", {})

    def get_hourly_dataframe(self) -> Optional[pd.DataFrame]:
        """Return next 24h as a DataFrame."""
        if not self.hourly or "time" not in self.hourly:
            return None
        try:
            df = pd.DataFrame(self.hourly)
            df["time"] = pd.to_datetime(df["time"])
            return df.head(24)
        except Exception as e:
            print(f"[WeatherTimeline] Hourly DF error: {e}")
            return None

    def get_daily_dataframe(self) -> Optional[pd.DataFrame]:
        """Return 7-day forecast as a DataFrame."""
        if not self.daily or "time" not in self.daily:
            return None
        try:
            df = pd.DataFrame(self.daily)
            df["time"] = pd.to_datetime(df["time"])
            return df
        except Exception as e:
            print(f"[WeatherTimeline] Daily DF error: {e}")
            return None

    def get_current_summary(self) -> dict:
        """Return a flat dict of current conditions for display."""
        w = self.weather
        return {
            "condition":    w.get("condition", "N/A"),
            "icon":         w.get("condition_icon", "❓"),
            "temp":         f"{w.get('temperature', '--')}°C",
            "feels_like":   f"{w.get('feels_like', '--')}°C",
            "humidity":     f"{w.get('humidity', '--')}%",
            "wind":         f"{w.get('wind_speed', '--')} km/h {w.get('wind_cardinal', '')}",
            "gusts":        f"{w.get('wind_gusts', '--')} km/h",
            "pressure":     f"{w.get('pressure', '--')} hPa",
            "rainfall":     f"{w.get('precipitation', '--')} mm",
            "cloud_cover":  f"{w.get('cloud_cover', '--')}%",
            "visibility":   self._fmt_visibility(w.get("visibility")),
            "beaufort":     f"Bft {w.get('beaufort_num', '--')} – {w.get('beaufort_desc', '')}",
            "sea_state":    w.get("sea_state", "N/A"),
            "risk":         w.get("marine_risk", "N/A"),
            "risk_color":   w.get("marine_risk_color", "#888"),
        }

    @staticmethod
    def _fmt_visibility(vis_m) -> str:
        if vis_m is None:
            return "N/A"
        if vis_m >= 10000:
            return f"{vis_m/1000:.0f}+ km"
        if vis_m >= 1000:
            return f"{vis_m/1000:.1f} km"
        return f"{int(vis_m)} m"
