#!/usr/bin/env python3
"""
CargoPulse — Persistent AIS background fetcher.

Maintains a long-lived WebSocket to AISStream.io and continuously
accumulates live vessel positions into the SQLite cache.

Streamlit reads from that cache on every page load → zero wait time.

Usage (from project root):
    python run_ais_background.py

Run this alongside Streamlit, or use start.sh to launch both together.
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time

import websockets
from dotenv import load_dotenv

load_dotenv()

# ── Paths resolved relative to this file ──────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

from db import cache

# ── Config ─────────────────────────────────────────────────────────────
AISSTREAM_URL      = "wss://stream.aisstream.io/v0/stream"
VESSEL_CACHE_KEY   = "vessels_snapshot"
WRITE_INTERVAL_S   = 30     # flush accumulated vessels to SQLite every 30 s
FIRST_WRITE_MIN    = 30     # also flush as soon as we have this many vessels
RECONNECT_DELAY_S  = 5      # base delay before reconnect attempt
MAX_RECONNECT_S    = 120    # cap exponential backoff at 2 min

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [AIS]  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ais_background")

# ── Load port bounding boxes ────────────────────────────────────────────
_PORTS_PATH = os.path.join(_ROOT, "db", "ports.json")
with open(_PORTS_PATH) as _f:
    _PORTS = json.load(_f)


def _make_bbox(lat: float, lon: float, radius: float = 0.5) -> list:
    return [
        [round(lat - radius, 4), round(lon - radius, 4)],
        [round(lat + radius, 4), round(lon + radius, 4)],
    ]


BOUNDING_BOXES = [_make_bbox(p["lat"], p["lon"]) for p in _PORTS]

# ── State ───────────────────────────────────────────────────────────────
_vessels: dict[str, dict] = {}   # mmsi → latest vessel dict
_running: bool = True


def _stop(sig, _frame) -> None:
    global _running
    log.info("Shutdown signal received — stopping after next cache write.")
    _running = False


signal.signal(signal.SIGINT,  _stop)
signal.signal(signal.SIGTERM, _stop)


# ── Parse AISstream message ─────────────────────────────────────────────
def _parse(raw: str) -> dict | None:
    try:
        msg = json.loads(raw)
        if msg.get("MessageType") != "PositionReport":
            return None
        meta = msg["MetaData"]
        pos  = msg["Message"]["PositionReport"]
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
    except (KeyError, TypeError, json.JSONDecodeError):
        return None


# ── Flush vessels to SQLite ─────────────────────────────────────────────
def _flush() -> None:
    vessel_list = list(_vessels.values())
    cache.set(VESSEL_CACHE_KEY, {"vessels": vessel_list})
    log.info(f"Cache updated — {len(vessel_list)} unique vessels stored.")


# ── Core streaming coroutine ────────────────────────────────────────────
async def _stream(api_key: str) -> None:
    subscription = {
        "APIKey":             api_key,
        "BoundingBoxes":      BOUNDING_BOXES,
        "FilterMessageTypes": ["PositionReport"],
    }

    async with websockets.connect(
        AISSTREAM_URL,
        ping_interval=20,
        open_timeout=15,
    ) as ws:
        await ws.send(json.dumps(subscription))
        log.info(f"Connected to AISStream — watching {len(_PORTS)} ports.")

        last_flush  = time.monotonic()
        first_flush = False

        async for raw in ws:
            if not _running:
                break

            vessel = _parse(raw)
            if vessel and vessel["mmsi"]:
                _vessels[vessel["mmsi"]] = vessel

            now = time.monotonic()

            # Flush early as soon as we have a meaningful first batch
            if not first_flush and len(_vessels) >= FIRST_WRITE_MIN:
                _flush()
                first_flush = True
                last_flush  = now

            # Then flush on the regular interval
            elif first_flush and (now - last_flush) >= WRITE_INTERVAL_S:
                _flush()
                last_flush = now


# ── Main loop with reconnect ────────────────────────────────────────────
async def main() -> None:
    api_key = os.getenv("AISSTREAM_API_KEY", "").strip()
    if not api_key:
        log.error("AISSTREAM_API_KEY is not set in .env — cannot connect.")
        sys.exit(1)

    delay = RECONNECT_DELAY_S
    log.info("CargoPulse AIS background fetcher starting…")

    while _running:
        try:
            await _stream(api_key)
            delay = RECONNECT_DELAY_S   # reset on clean disconnect
        except (websockets.WebSocketException, OSError, asyncio.TimeoutError) as exc:
            if not _running:
                break
            log.warning(f"Connection lost ({exc.__class__.__name__}: {exc}). "
                        f"Reconnecting in {delay}s…")
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_S)
        except Exception as exc:
            if not _running:
                break
            log.error(f"Unexpected error: {exc}. Reconnecting in {delay}s…")
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_S)

    # Final flush on clean shutdown
    if _vessels:
        log.info("Writing final snapshot before exit…")
        _flush()
    log.info("AIS background fetcher stopped.")


if __name__ == "__main__":
    asyncio.run(main())
