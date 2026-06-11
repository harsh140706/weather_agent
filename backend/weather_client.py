"""
weather_client.py
Open-Meteo API client — synchronous + async-ready.

Fixes:
• SSL handshake failures (SSLEOFError)
• Retry handling for 502/503/504
• Better request stability
• Connection pooling
• Safer timeout handling
• Keeps Claude's async + batch architecture
"""

import asyncio
import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "weather_code",
]


class WeatherClient:
    """
    HTTP client for Open-Meteo.

    Sync path:
        fetch_weather()
        fetch_current_only()

    Async path:
        fetch_weather_async()

    Batch path:
        fetch_batch()
    """

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

        self.session = requests.Session()

        retry_strategy = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20,
        )

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MaritimeWeatherAgent/1.0"
        })

    # ─────────────────────────────────────────────
    # Sync
    # ─────────────────────────────────────────────

    def fetch_weather(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[dict]:
        """
        Full weather fetch:
        current + hourly + daily 7-day forecast
        """

        params = self._build_params(
            latitude,
            longitude,
            full=True
        )

        try:
            response = self.session.get(
                OPEN_METEO_URL,
                params=params,
                timeout=self.timeout,
                verify=True,
            )

            response.raise_for_status()

            data = response.json()

            logger.info(
                f"[WeatherClient] Success "
                f"({latitude:.4f}, {longitude:.4f})"
            )

            return data

        except requests.exceptions.Timeout:
            logger.warning(
                f"[WeatherClient] Timeout "
                f"({latitude}, {longitude})"
            )

        except requests.exceptions.SSLError as e:
            logger.error(
                f"[WeatherClient] SSL Error: {e}"
            )

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"[WeatherClient] HTTP Error: {e}"
            )

        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"[WeatherClient] Connection Error: {e}"
            )

        except requests.exceptions.RequestException as e:
            logger.error(
                f"[WeatherClient] Request Error: {e}"
            )

        except Exception as e:
            logger.exception(
                f"[WeatherClient] Unexpected Error: {e}"
            )

        return None

    def fetch_current_only(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[dict]:
        """
        Lightweight fetch for fleet overview.
        """

        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "current": ",".join(CURRENT_PARAMS),
            "timezone": "auto",
        }

        try:
            response = self.session.get(
                OPEN_METEO_URL,
                params=params,
                timeout=self.timeout,
                verify=True,
            )

            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(
                f"[WeatherClient] Current weather error: {e}"
            )
            return None

    # ─────────────────────────────────────────────
    # Batch
    # ─────────────────────────────────────────────

    def fetch_batch(
        self,
        vessels: list[dict]
    ) -> dict[str, Optional[dict]]:
        """
        Batch weather fetching.

        Deduplicates vessels by 0.5°
        grid cells to reduce API calls.
        """

        cell_cache: dict[str, dict] = {}
        results: dict[str, Optional[dict]] = {}

        for vessel in vessels:

            mmsi = str(vessel.get("mmsi", ""))

            lat = (
                round(float(vessel.get("latitude", 0)) * 2)
                / 2
            )

            lon = (
                round(float(vessel.get("longitude", 0)) * 2)
                / 2
            )

            key = f"{lat},{lon}"

            if key not in cell_cache:
                cell_cache[key] = self.fetch_weather(
                    lat,
                    lon
                )

            results[mmsi] = cell_cache[key]

        logger.info(
            f"[WeatherClient] "
            f"{len(vessels)} vessels → "
            f"{len(cell_cache)} API calls"
        )

        return results

    # ─────────────────────────────────────────────
    # Async
    # ─────────────────────────────────────────────

    async def fetch_weather_async(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[dict]:
        """
        Async wrapper around sync request.
        """

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            self.fetch_weather,
            latitude,
            longitude,
        )

    async def fetch_batch_async(
        self,
        vessels: list[dict]
    ) -> dict[str, Optional[dict]]:

        cell_map: dict[str, tuple[float, float]] = {}

        for vessel in vessels:

            lat = (
                round(float(vessel.get("latitude", 0)) * 2)
                / 2
            )

            lon = (
                round(float(vessel.get("longitude", 0)) * 2)
                / 2
            )

            cell_map[f"{lat},{lon}"] = (
                lat,
                lon,
            )

        tasks = {
            key: asyncio.create_task(
                self.fetch_weather_async(
                    lat,
                    lon
                )
            )
            for key, (lat, lon)
            in cell_map.items()
        }

        cell_results = {}

        for key, task in tasks.items():
            cell_results[key] = await task

        results = {}

        for vessel in vessels:

            mmsi = str(vessel.get("mmsi", ""))

            lat = (
                round(float(vessel.get("latitude", 0)) * 2)
                / 2
            )

            lon = (
                round(float(vessel.get("longitude", 0)) * 2)
                / 2
            )

            results[mmsi] = cell_results.get(
                f"{lat},{lon}"
            )

        return results

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _build_params(
        self,
        latitude: float,
        longitude: float,
        full: bool = True
    ) -> dict:

        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "current": ",".join(CURRENT_PARAMS),
            "timezone": "auto",
            "forecast_days": 7,
        }

        if full:
            params["hourly"] = ",".join(HOURLY_PARAMS)
            params["daily"] = ",".join(DAILY_PARAMS)

        return params
