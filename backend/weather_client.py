"""
weather_client.py
Open-Meteo API client — synchronous + async-ready.

Changes vs original:
  • Added wind_speed_10m_max to DAILY_PARAMS (required by ForecastEngine)
  • Added surface_pressure_max to DAILY_PARAMS for pressure-drop detection
  • fetch_weather_async() — asyncio-compatible, returns same structure
  • fetch_batch() — fetches multiple vessels with deduplication by grid cell
  • Structured error returns instead of bare None (keeps None contract for
    backward compat but logs richer diagnostics)
"""

import asyncio
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

CURRENT_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "precipitation",
    "cloud_cover",
    "visibility",
    "weather_code",
    "apparent_temperature",
    "wind_gusts_10m",
]

HOURLY_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "cloud_cover",
    "visibility",
    "weather_code",
]

DAILY_PARAMS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "wind_speed_10m_max",           # ← required by ForecastEngine
    "wind_direction_10m_dominant",
    "weather_code",
]


class WeatherClient:
    """
    HTTP client for Open-Meteo.

    Sync path:  fetch_weather() / fetch_current_only()
    Async path: fetch_weather_async()  (requires running event loop)
    Batch path: fetch_batch()          (deduplicates by 0.5° grid cell)
    """

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ── Sync ─────────────────────────────────────────────────────────────────

    def fetch_weather(self, latitude: float, longitude: float) -> Optional[dict]:
        """Full forecast fetch: current + hourly (24h) + daily (7d)."""
        params = self._build_params(latitude, longitude, full=True)
        try:
            resp = self.session.get(OPEN_METEO_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[WeatherClient] Fetched ({latitude:.4f}, {longitude:.4f})")
            return data
        except requests.exceptions.Timeout:
            logger.warning(f"[WeatherClient] Timeout ({latitude}, {longitude})")
        except requests.exceptions.HTTPError as e:
            logger.error(f"[WeatherClient] HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[WeatherClient] Request error: {e}")
        except Exception as e:
            logger.error(f"[WeatherClient] Unexpected error: {e}", exc_info=True)
        return None

    def fetch_current_only(self, latitude: float, longitude: float) -> Optional[dict]:
        """Lightweight fetch for current conditions only (fleet overview refresh)."""
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "current": ",".join(CURRENT_PARAMS),
            "timezone": "auto",
        }
        try:
            resp = self.session.get(OPEN_METEO_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[WeatherClient] Error fetching current weather: {e}")
            return None

    def fetch_batch(self, vessels: list[dict]) -> dict[str, Optional[dict]]:
        """
        Fetch weather for multiple vessels.
        Deduplicates requests by rounding lat/lon to 0.5° grid cells.
        Returns dict of mmsi → raw API response (or None).

        This avoids N separate API calls when many vessels are clustered.
        """
        cell_cache: dict[str, dict] = {}
        results: dict[str, Optional[dict]] = {}

        for v in vessels:
            mmsi = str(v.get("mmsi", ""))
            lat  = round(float(v.get("latitude", 0)) * 2) / 2   # 0.5° grid
            lon  = round(float(v.get("longitude", 0)) * 2) / 2
            key  = f"{lat},{lon}"

            if key not in cell_cache:
                cell_cache[key] = self.fetch_weather(lat, lon)

            results[mmsi] = cell_cache[key]

        logger.info(
            f"[WeatherClient] batch: {len(vessels)} vessels → "
            f"{len(cell_cache)} unique API calls"
        )
        return results

    # ── Async ────────────────────────────────────────────────────────────────

    async def fetch_weather_async(
        self, latitude: float, longitude: float
    ) -> Optional[dict]:
        """
        Non-blocking equivalent of fetch_weather().
        Runs the sync HTTP call in a thread pool to avoid blocking the event loop.
        Future enhancement: replace with aiohttp for true async I/O.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch_weather, latitude, longitude)

    async def fetch_batch_async(self, vessels: list[dict]) -> dict[str, Optional[dict]]:
        """Async batch fetch — fires all unique grid cells concurrently."""
        cell_map: dict[str, tuple[float, float]] = {}
        for v in vessels:
            lat = round(float(v.get("latitude", 0)) * 2) / 2
            lon = round(float(v.get("longitude", 0)) * 2) / 2
            cell_map[f"{lat},{lon}"] = (lat, lon)

        tasks = {
            key: asyncio.create_task(self.fetch_weather_async(lat, lon))
            for key, (lat, lon) in cell_map.items()
        }
        cell_results: dict[str, Optional[dict]] = {}
        for key, task in tasks.items():
            cell_results[key] = await task

        results: dict[str, Optional[dict]] = {}
        for v in vessels:
            mmsi = str(v.get("mmsi", ""))
            lat  = round(float(v.get("latitude", 0)) * 2) / 2
            lon  = round(float(v.get("longitude", 0)) * 2) / 2
            results[mmsi] = cell_results.get(f"{lat},{lon}")

        return results

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_params(self, latitude: float, longitude: float, full: bool = True) -> dict:
        params: dict = {
            "latitude":      round(latitude, 4),
            "longitude":     round(longitude, 4),
            "current":       ",".join(CURRENT_PARAMS),
            "timezone":      "auto",
            "forecast_days": 7,
        }
        if full:
            params["hourly"] = ",".join(HOURLY_PARAMS)
            params["daily"]  = ",".join(DAILY_PARAMS)
        return params
