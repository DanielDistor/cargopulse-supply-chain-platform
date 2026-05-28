import asyncio
import json
import os
import websockets
from db import cache

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
VESSEL_CACHE_KEY = "vessels_snapshot"
TTL = 15 * 60  # 15 minutes


def make_port_bounding_box(lat: float, lon: float, radius_deg: float = 0.5) -> list:
    """Return [[min_lat, min_lon], [max_lat, max_lon]] bounding box."""
    return [
        [round(lat - radius_deg, 4), round(lon - radius_deg, 4)],
        [round(lat + radius_deg, 4), round(lon + radius_deg, 4)],
    ]


def parse_position_report(message: dict) -> dict | None:
    """Extract clean vessel dict from an AISstream PositionReport message."""
    try:
        if message.get("MessageType") != "PositionReport":
            return None
        meta = message["MetaData"]
        pos = message["Message"]["PositionReport"]
        return {
            "mmsi": str(meta.get("MMSI", "")),
            "name": meta.get("ShipName", "Unknown").strip(),
            "lat": pos.get("Latitude"),
            "lon": pos.get("Longitude"),
            "speed": pos.get("Sog"),
            "heading": pos.get("TrueHeading"),
            "status": pos.get("NavigationalStatus"),
            "timestamp": meta.get("time_utc", ""),
        }
    except (KeyError, TypeError):
        return None


async def _fetch_snapshot(bounding_boxes: list, duration_seconds: int) -> list[dict]:
    """Connect to AISstream, collect vessels for duration_seconds, return list."""
    api_key = os.getenv("AISSTREAM_API_KEY", "")
    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": bounding_boxes,
        "FilterMessageTypes": ["PositionReport"],
    }
    vessels: dict[str, dict] = {}
    try:
        async with websockets.connect(AISSTREAM_URL, ping_interval=20) as ws:
            await ws.send(json.dumps(subscription))
            deadline = asyncio.get_event_loop().time() + duration_seconds
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    vessel = parse_position_report(json.loads(raw))
                    if vessel and vessel["mmsi"]:
                        vessels[vessel["mmsi"]] = vessel
                except asyncio.TimeoutError:
                    continue
    except Exception:
        pass
    return list(vessels.values())


def get_vessels(bounding_boxes: list, duration_seconds: int = 5) -> list[dict]:
    """
    Return cached vessel snapshot or fetch a fresh one.
    Falls back to stale cache if API is unreachable.
    """
    cached = cache.get(VESSEL_CACHE_KEY, TTL)
    if cached is not None:
        return cached.get("vessels", [])

    try:
        vessels = asyncio.run(_fetch_snapshot(bounding_boxes, duration_seconds))
    except RuntimeError:
        # Streamlit may already have an event loop in some environments
        loop = asyncio.new_event_loop()
        vessels = loop.run_until_complete(
            _fetch_snapshot(bounding_boxes, duration_seconds)
        )
        loop.close()

    if vessels:
        cache.set(VESSEL_CACHE_KEY, {"vessels": vessels})
        return vessels

    # API failed — return stale data with whatever we have
    stale = cache.get_stale(VESSEL_CACHE_KEY)
    return stale.get("vessels", []) if stale else []
