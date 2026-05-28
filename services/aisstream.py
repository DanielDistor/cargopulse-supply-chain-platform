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
    """Connect to AISstream, collect vessels for duration_seconds, return list.

    Subscribes to both PositionReport and ShipStaticData so vessel type codes
    are captured whenever they arrive within the fetch window.
    """
    api_key = os.getenv("AISSTREAM_API_KEY", "")
    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": bounding_boxes,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData", "ClassBCSStaticData"],
    }
    vessels: dict[str, dict] = {}
    vessel_types: dict[str, int] = {}
    try:
        async with websockets.connect(AISSTREAM_URL, ping_interval=20) as ws:
            await ws.send(json.dumps(subscription))
            deadline = asyncio.get_event_loop().time() + duration_seconds
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw  = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg  = json.loads(raw)
                    mtype = msg.get("MessageType", "")
                    meta  = msg.get("MetaData", {})
                    mmsi  = str(meta.get("MMSI", ""))

                    if mtype == "PositionReport":
                        vessel = parse_position_report(msg)
                        if vessel and vessel["mmsi"]:
                            vessels[vessel["mmsi"]] = vessel

                    elif mtype in ("ShipStaticData", "ClassBCSStaticData"):
                        static = msg.get("Message", {}).get(mtype, {})
                        code   = static.get("Type")
                        if mmsi and code is not None:
                            vessel_types[mmsi] = int(code)

                except asyncio.TimeoutError:
                    continue
    except Exception:
        pass

    # Merge type codes into vessel dicts
    result = []
    for mmsi, v in vessels.items():
        if mmsi in vessel_types:
            v = dict(v)
            v["vessel_type_code"] = vessel_types[mmsi]
        result.append(v)
    return result


def get_vessels(bounding_boxes: list, duration_seconds: int = 3) -> list[dict]:
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

    # Always cache — even empty results — so subsequent loads are instant
    cache.set(VESSEL_CACHE_KEY, {"vessels": vessels})

    if vessels:
        return vessels

    # API failed — return stale data with whatever we have
    stale = cache.get_stale(VESSEL_CACHE_KEY)
    return stale.get("vessels", []) if stale else []
