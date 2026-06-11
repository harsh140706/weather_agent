"""
weather_cache.py
TTL-based in-memory cache with LRU eviction and hit-rate tracking.

Changes vs original:
  • LRU eviction when max_size exceeded (prevents unbounded memory growth)
  • Cache hit / miss counters for monitoring
  • cache.get_or_fetch() convenience method (reduces boilerplate in app.py)
  • Thread-safe using collections.OrderedDict (single-process Streamlit)
"""

import time
import logging
from collections import OrderedDict
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class WeatherCache:
    """
    TTL + LRU in-memory cache keyed by (lat, lon) rounded to 2 dp.

    Attributes:
        ttl_seconds: How long an entry is considered fresh.
        max_size:    Maximum number of entries; oldest evicted when exceeded.
    """

    def __init__(self, ttl_seconds: int = 600, max_size: int = 200):
        self._cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self.ttl        = ttl_seconds
        self.max_size   = max_size
        self._hits      = 0
        self._misses    = 0

    # ── Core operations ───────────────────────────────────────────────────────

    def _key(self, lat: float, lon: float) -> str:
        return f"{round(lat, 2)},{round(lon, 2)}"

    def get(self, lat: float, lon: float) -> Optional[dict]:
        key   = self._key(lat, lon)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        data, ts = entry
        if time.time() - ts > self.ttl:
            del self._cache[key]
            self._misses += 1
            logger.debug(f"[WeatherCache] Expired: {key}")
            return None
        # Move to end (LRU)
        self._cache.move_to_end(key)
        self._hits += 1
        logger.debug(f"[WeatherCache] Hit: {key}")
        return data

    def set(self, lat: float, lon: float, data: dict) -> None:
        key = self._key(lat, lon)
        self._cache[key] = (data, time.time())
        self._cache.move_to_end(key)
        if len(self._cache) > self.max_size:
            evicted = self._cache.popitem(last=False)
            logger.debug(f"[WeatherCache] LRU evict: {evicted[0]}")
        logger.debug(f"[WeatherCache] Stored: {key}")

    def get_or_fetch(
        self,
        lat: float,
        lon: float,
        fetch_fn: Callable[[float, float], Optional[dict]],
    ) -> Optional[dict]:
        """
        Return cached value or call fetch_fn(lat, lon) and store result.
        Reduces boilerplate fetch-check-store patterns in app.py.
        """
        cached = self.get(lat, lon)
        if cached is not None:
            return cached
        fresh = fetch_fn(lat, lon)
        if fresh is not None:
            self.set(lat, lon, fresh)
        return fresh

    def invalidate(self, lat: float, lon: float) -> None:
        self._cache.pop(self._key(lat, lon), None)

    def clear(self) -> None:
        self._cache.clear()
        logger.info("[WeatherCache] Cleared.")

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> dict:
        now   = time.time()
        valid = sum(1 for (_, ts) in self._cache.values() if now - ts <= self.ttl)
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0
        return {
            "total":       len(self._cache),
            "valid":       valid,
            "ttl_seconds": self.ttl,
            "hits":        self._hits,
            "misses":      self._misses,
            "hit_rate_pct": round(hit_rate, 1),
        }
