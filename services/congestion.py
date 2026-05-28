import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from db import cache
from services import weather as weather_svc

TTL = 15 * 60  # 15 minutes
PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
CONGESTION_CACHE_KEY = "all_port_congestion"


def load_ports() -> list[dict]:
    with open(PORTS_PATH) as f:
        return json.load(f)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def count_vessels_near_port(
    vessels: list[dict], port_lat: float, port_lon: float, radius_km: float = 50.0
) -> int:
    """Count vessels within radius_km of a port coordinate."""
    count = 0
    for v in vessels:
        if v.get("lat") is None or v.get("lon") is None:
            continue
        if haversine_km(v["lat"], v["lon"], port_lat, port_lon) <= radius_km:
            count += 1
    return count


def compute_congestion_score(
    waiting_vessels: int, capacity_baseline: int, wave_height_m: float | None
) -> int:
    """Return congestion score 0–100."""
    penalty = weather_svc.weather_penalty(wave_height_m)
    ratio = waiting_vessels / max(capacity_baseline, 1)
    raw = min(ratio * 100 * penalty, 100)
    return round(raw)


def congestion_label(score: int) -> str:
    if score <= 30:
        return "Clear"
    if score <= 60:
        return "Moderate"
    if score <= 85:
        return "High"
    return "Critical"


def congestion_color(score: int) -> str:
    if score <= 30:
        return "#4caf50"
    if score <= 60:
        return "#ffb74d"
    if score <= 85:
        return "#ef5350"
    return "#212121"


def get_all_port_congestion(vessels: list[dict]) -> list[dict]:
    """
    Score every port. Returns list sorted by score descending.

    Warm path:  one SQLite read  (~ms)
    Cold path:  all 50 weather fetches run in parallel (10 workers),
                then whole result is cached for 15 minutes.
    """
    cached = cache.get(CONGESTION_CACHE_KEY, TTL)
    if cached:
        return cached.get("data", [])

    ports = load_ports()

    def _score_port(port: dict) -> dict:
        vessel_count = count_vessels_near_port(vessels, port["lat"], port["lon"])
        w = weather_svc.get_marine_weather(port["lat"], port["lon"])
        score = compute_congestion_score(
            vessel_count, port["capacity_baseline"], w.get("wave_height_m")
        )
        return {
            "name": port["name"],
            "country": port["country"],
            "region": port["region"],
            "lat": port["lat"],
            "lon": port["lon"],
            "vessel_count": vessel_count,
            "capacity_baseline": port["capacity_baseline"],
            "score": score,
            "label": congestion_label(score),
            "color": congestion_color(score),
            "wave_height_m": w.get("wave_height_m"),
        }

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(_score_port, ports))

    results.sort(key=lambda x: x["score"], reverse=True)
    cache.set(CONGESTION_CACHE_KEY, {"data": results})
    return results
