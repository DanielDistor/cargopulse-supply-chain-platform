import httpx
from db import cache

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
TTL = 3 * 3600  # 3 hours


def weather_penalty(wave_height_m: float | None) -> float:
    """Convert wave height in metres to a congestion penalty multiplier (1.0–1.5)."""
    if wave_height_m is None:
        return 1.0
    if wave_height_m < 1.0:
        return 1.0
    if wave_height_m < 2.0:
        return 1.1
    if wave_height_m < 3.0:
        return 1.25
    return 1.5


def get_marine_weather(lat: float, lon: float) -> dict:
    """
    Fetch current marine weather for a coordinate.
    Returns dict with wave_height_m, wave_direction_deg, etc.
    Falls back to stale cache or null dict on failure.
    """
    cache_key = f"weather_{lat:.2f}_{lon:.2f}"
    cached = cache.get(cache_key, TTL)
    if cached:
        return cached

    _null = {
        "wave_height_m": None,
        "wave_direction_deg": None,
        "wave_period_s": None,
        "wind_wave_height_m": None,
        "current_velocity_kn": None,
        "lat": lat,
        "lon": lon,
    }

    try:
        resp = httpx.get(
            MARINE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "wave_height,wave_direction,wave_period,"
                    "wind_wave_height,ocean_current_velocity"
                ),
            },
            timeout=5,
        )
        resp.raise_for_status()
        current = resp.json().get("current", {})
        result = {
            "wave_height_m": current.get("wave_height"),
            "wave_direction_deg": current.get("wave_direction"),
            "wave_period_s": current.get("wave_period"),
            "wind_wave_height_m": current.get("wind_wave_height"),
            "current_velocity_kn": current.get("ocean_current_velocity"),
            "lat": lat,
            "lon": lon,
        }
        cache.set(cache_key, result)
        return result
    except Exception:
        return cache.get_stale(cache_key) or _null
