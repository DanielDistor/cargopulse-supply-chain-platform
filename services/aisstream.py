import asyncio
import concurrent.futures
import json
import os
import time
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
            "mmsi":      str(meta.get("MMSI", "")),
            "name":      meta.get("ShipName", "Unknown").strip(),
            "lat":       pos.get("Latitude"),
            "lon":       pos.get("Longitude"),
            "speed":     pos.get("Sog"),
            "heading":   pos.get("TrueHeading"),
            "status":    pos.get("NavigationalStatus"),
            "timestamp": meta.get("time_utc", ""),
        }
    except (KeyError, TypeError):
        return None


async def _fetch_snapshot(bounding_boxes: list, duration_seconds: int) -> list[dict]:
    """Open a WebSocket to AISstream, collect vessels for duration_seconds."""
    api_key = os.getenv("AISSTREAM_API_KEY", "")
    subscription = {
        "APIKey":             api_key,
        "BoundingBoxes":      bounding_boxes,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData", "ClassBCSStaticData"],
    }
    vessels: dict[str, dict] = {}
    vessel_types: dict[str, int] = {}

    try:
        async with websockets.connect(
            AISSTREAM_URL,
            ping_interval=20,
            open_timeout=10,
        ) as ws:
            await ws.send(json.dumps(subscription))
            deadline = time.monotonic() + duration_seconds   # no asyncio clock — safe everywhere

            while time.monotonic() < deadline:
                try:
                    raw   = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg   = json.loads(raw)
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

    # Merge type codes into position records
    result = []
    for mmsi, v in vessels.items():
        if mmsi in vessel_types:
            v = dict(v)
            v["vessel_type_code"] = vessel_types[mmsi]
        result.append(v)
    return result


def _run_fetch(bounding_boxes: list, duration_seconds: int) -> list[dict]:
    """
    Execute the async fetch in a *fresh thread with its own event loop*.

    This is the only approach that works reliably across all Streamlit
    versions — both local and Streamlit Cloud — regardless of whether the
    calling thread already has a running event loop.
    """
    def _in_thread() -> list[dict]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_fetch_snapshot(bounding_boxes, duration_seconds))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_in_thread)
        try:
            return future.result(timeout=duration_seconds + 10)
        except Exception:
            return []


def get_vessels(bounding_boxes: list, duration_seconds: int = 5) -> list[dict]:
    """
    Return a vessel snapshot from cache, or fetch a fresh one.

    Key behaviours:
    - Empty fetches are NOT cached — a transient API hiccup won't lock the
      page out for the full 15-minute TTL.
    - If the fetch fails, stale cached data is returned so the page never
      goes completely blank when the API is temporarily unavailable.
    """
    cached = cache.get(VESSEL_CACHE_KEY, TTL)
    if cached is not None:
        return cached.get("vessels", [])

    vessels = _run_fetch(bounding_boxes, duration_seconds)

    if vessels:
        cache.set(VESSEL_CACHE_KEY, {"vessels": vessels})
        return vessels

    # Fetch returned nothing — serve stale data rather than a blank page
    stale = cache.get_stale(VESSEL_CACHE_KEY)
    return stale.get("vessels", []) if stale else []
