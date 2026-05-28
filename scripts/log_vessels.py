"""
Standalone vessel logger for GitHub Actions.

Fetches a 15-second AIS snapshot across all configured ports,
counts vessels with valid coordinates, logs the total to Supabase
(vessel_activity), and upserts individual MMSIs for the day
(vessel_daily) so the 7-day chart shows true distinct vessel counts.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import websockets
from dotenv import load_dotenv

# Allow importing db.supabase_logger from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_logger

load_dotenv()

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
PORTS_PATH    = Path(__file__).parent.parent / "db" / "ports.json"
FETCH_SECONDS = 15


def _bounding_box(lat: float, lon: float, radius: float = 0.5) -> list:
    return [[lat - radius, lon - radius], [lat + radius, lon + radius]]


async def _fetch(duration: int) -> tuple[int, list[str]]:
    """Returns (vessel_count, list_of_mmsis)."""
    api_key = os.getenv("AISSTREAM_API_KEY", "")
    if not api_key:
        print("ERROR: AISSTREAM_API_KEY not set")
        return 0, []

    with open(PORTS_PATH) as f:
        ports = json.load(f)

    bboxes = [_bounding_box(p["lat"], p["lon"]) for p in ports]
    subscription = {
        "APIKey":             api_key,
        "BoundingBoxes":      bboxes,
        "FilterMessageTypes": ["PositionReport"],
    }

    vessels: dict[str, bool] = {}
    try:
        async with websockets.connect(
            AISSTREAM_URL, ping_interval=20, open_timeout=10
        ) as ws:
            await ws.send(json.dumps(subscription))
            deadline = time.monotonic() + duration

            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg = json.loads(raw)
                    if msg.get("MessageType") == "PositionReport":
                        meta = msg.get("MetaData", {})
                        pos  = msg.get("Message", {}).get("PositionReport", {})
                        mmsi = str(meta.get("MMSI", ""))
                        lat  = pos.get("Latitude")
                        lon  = pos.get("Longitude")
                        if mmsi and lat is not None and lon is not None:
                            vessels[mmsi] = True
                except asyncio.TimeoutError:
                    continue
    except Exception as e:
        print(f"AIS fetch error: {e}")

    mmsis = list(vessels.keys())
    return len(mmsis), mmsis


def main() -> None:
    count, mmsis = asyncio.run(_fetch(FETCH_SECONDS))
    print(f"Vessel count: {count}")

    if count > 0:
        supabase_logger.log_snapshot(count)
        print("Logged snapshot to vessel_activity ✓")

        supabase_logger.log_vessel_mmsis(mmsis)
        print(f"Upserted {len(mmsis)} MMSIs to vessel_daily ✓")
    else:
        print("No vessels found — skipping log")


if __name__ == "__main__":
    main()
