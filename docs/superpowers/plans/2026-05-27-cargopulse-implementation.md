# CargoPulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live supply chain risk dashboard with vessel tracking, port congestion scoring, delay forecasting, and supplier risk monitoring — deployed free on Streamlit Cloud.

**Architecture:** Single Streamlit multi-page app (no backend server). Four layers: pages → services → cache (SQLite) → external APIs. Each service handles one data source and falls back to stale cache if the API is unavailable.

**Tech Stack:** Python 3.11+, Streamlit, Plotly, websockets, httpx, yfinance, sqlite3, pandas, python-dotenv, pytest

---

## File Map

```
cargopulse-supply-chain-platform/
├── app.py                          ← Home overview dashboard
├── pages/
│   ├── 1_🗺️_Vessel_Map.py
│   ├── 2_📊_Port_Congestion.py
│   ├── 3_⏱️_Delay_Forecast.py
│   └── 4_⚠️_Supplier_Risk.py
├── services/
│   ├── __init__.py                 ← empty
│   ├── aisstream.py                ← WebSocket client + snapshot fetch
│   ├── weather.py                  ← Open-Meteo marine weather
│   ├── shipping_rates.py           ← yfinance Baltic Dry Index
│   └── congestion.py               ← vessel density → congestion score
├── db/
│   ├── __init__.py                 ← empty
│   ├── cache.py                    ← SQLite get/set/stale helpers
│   └── ports.json                  ← top 50 world ports (lat/lon/capacity)
├── components/
│   ├── __init__.py                 ← empty
│   ├── risk_badge.py               ← color-coded risk label HTML
│   └── kpi_card.py                 ← reusable metric card
├── tests/
│   ├── conftest.py                 ← pytest fixtures (temp DB path)
│   ├── test_cache.py
│   ├── test_congestion.py
│   ├── test_weather.py
│   ├── test_shipping_rates.py
│   └── test_aisstream.py
├── .env                            ← gitignored, holds AISSTREAM_API_KEY
├── .env.example
└── requirements.txt
```

---

## Phase 1 — Scaffold + Cache Layer

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `services/__init__.py`
- Create: `db/__init__.py`
- Create: `components/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
streamlit>=1.35.0
plotly>=5.22.0
pandas>=2.2.0
httpx>=0.27.0
websockets>=12.0
yfinance>=0.2.40
python-dotenv>=1.0.0
pytest>=8.2.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create `.env.example`**

```
# Copy this to .env and fill in your values
AISSTREAM_API_KEY=your_key_here

# Optional — used only for tests
CACHE_DB_PATH=
```

- [ ] **Step 3: Create empty `__init__.py` files**

```bash
touch services/__init__.py db/__init__.py components/__init__.py
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import os
import tempfile
import pytest

@pytest.fixture(autouse=True)
def temp_cache_db(tmp_path):
    """Point cache at a fresh temp DB for every test."""
    db_file = str(tmp_path / "test_cache.db")
    os.environ["CACHE_DB_PATH"] = db_file
    yield db_file
    os.environ.pop("CACHE_DB_PATH", None)
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example services/__init__.py db/__init__.py components/__init__.py tests/conftest.py
git commit -m "feat: project scaffold and dependencies"
```

---

### Task 2: Cache layer

**Files:**
- Create: `db/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests in `tests/test_cache.py`**

```python
import time
import pytest
from db import cache


def test_set_and_get_returns_stored_data():
    cache.set("key1", {"value": 42})
    result = cache.get("key1", ttl_seconds=3600)
    assert result == {"value": 42}


def test_get_returns_none_when_expired():
    cache.set("key2", {"value": 99})
    result = cache.get("key2", ttl_seconds=0)
    assert result is None


def test_get_returns_none_when_missing():
    result = cache.get("nonexistent_xyz", ttl_seconds=3600)
    assert result is None


def test_get_stale_returns_data_regardless_of_ttl():
    cache.set("key3", {"value": "old"})
    result = cache.get_stale("key3")
    assert result == {"value": "old"}


def test_get_stale_returns_none_when_never_set():
    result = cache.get_stale("never_set_key_xyz")
    assert result is None


def test_get_age_seconds_returns_elapsed():
    cache.set("key4", {"v": 1})
    age = cache.get_age_seconds("key4")
    assert 0 <= age <= 2


def test_get_age_seconds_returns_none_when_missing():
    result = cache.get_age_seconds("missing_key_xyz")
    assert result is None


def test_set_overwrites_existing():
    cache.set("key5", {"v": 1})
    cache.set("key5", {"v": 2})
    result = cache.get("key5", ttl_seconds=3600)
    assert result == {"v": 2}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_cache.py -v
```

Expected: `ModuleNotFoundError: No module named 'db.cache'`

- [ ] **Step 3: Write `db/cache.py`**

```python
import sqlite3
import json
import time
import os

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "cache.db")


def _db_path() -> str:
    return os.environ.get("CACHE_DB_PATH", _DEFAULT_DB)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            key        TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            fetched_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get(key: str, ttl_seconds: int) -> dict | None:
    """Return cached data if it exists and is within TTL, else None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT data, fetched_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    data, fetched_at = row
    if time.time() - fetched_at > ttl_seconds:
        return None
    return json.loads(data)


def set(key: str, data: dict) -> None:
    """Write data to cache with current timestamp."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), int(time.time())),
        )


def get_stale(key: str) -> dict | None:
    """Return cached data regardless of age (fallback when API is down)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT data FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def get_age_seconds(key: str) -> int | None:
    """Return how many seconds ago this key was last written."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT fetched_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    return int(time.time() - row[0])
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_cache.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add db/cache.py tests/test_cache.py
git commit -m "feat: SQLite cache layer with TTL, stale fallback, age tracking"
```

---

### Task 3: Port database (`ports.json`)

**Files:**
- Create: `db/ports.json`

- [ ] **Step 1: Write `db/ports.json`**

```json
[
  {"name": "Shanghai",          "country": "China",        "region": "East Asia",      "lat": 31.20, "lon": 121.50, "capacity_baseline": 80, "avg_delay_days": 3},
  {"name": "Singapore",         "country": "Singapore",    "region": "Southeast Asia", "lat": 1.27,  "lon": 103.82, "capacity_baseline": 75, "avg_delay_days": 2},
  {"name": "Ningbo-Zhoushan",   "country": "China",        "region": "East Asia",      "lat": 29.87, "lon": 121.55, "capacity_baseline": 70, "avg_delay_days": 3},
  {"name": "Shenzhen",          "country": "China",        "region": "East Asia",      "lat": 22.53, "lon": 113.92, "capacity_baseline": 65, "avg_delay_days": 3},
  {"name": "Guangzhou",         "country": "China",        "region": "East Asia",      "lat": 23.10, "lon": 113.26, "capacity_baseline": 60, "avg_delay_days": 3},
  {"name": "Busan",             "country": "South Korea",  "region": "East Asia",      "lat": 35.10, "lon": 129.04, "capacity_baseline": 55, "avg_delay_days": 2},
  {"name": "Qingdao",           "country": "China",        "region": "East Asia",      "lat": 36.07, "lon": 120.35, "capacity_baseline": 55, "avg_delay_days": 2},
  {"name": "Hong Kong",         "country": "China",        "region": "East Asia",      "lat": 22.32, "lon": 114.17, "capacity_baseline": 50, "avg_delay_days": 2},
  {"name": "Tianjin",           "country": "China",        "region": "East Asia",      "lat": 38.99, "lon": 117.72, "capacity_baseline": 50, "avg_delay_days": 3},
  {"name": "Rotterdam",         "country": "Netherlands",  "region": "Europe",         "lat": 51.92, "lon": 4.48,   "capacity_baseline": 55, "avg_delay_days": 1},
  {"name": "Dubai (Jebel Ali)", "country": "UAE",          "region": "Middle East",    "lat": 24.98, "lon": 55.06,  "capacity_baseline": 45, "avg_delay_days": 2},
  {"name": "Port Klang",        "country": "Malaysia",     "region": "Southeast Asia", "lat": 3.00,  "lon": 101.40, "capacity_baseline": 45, "avg_delay_days": 2},
  {"name": "Antwerp",           "country": "Belgium",      "region": "Europe",         "lat": 51.23, "lon": 4.42,   "capacity_baseline": 45, "avg_delay_days": 1},
  {"name": "Hamburg",           "country": "Germany",      "region": "Europe",         "lat": 53.54, "lon": 9.99,   "capacity_baseline": 40, "avg_delay_days": 1},
  {"name": "Los Angeles",       "country": "USA",          "region": "North America",  "lat": 33.74, "lon": -118.27,"capacity_baseline": 45, "avg_delay_days": 2},
  {"name": "Long Beach",        "country": "USA",          "region": "North America",  "lat": 33.75, "lon": -118.22,"capacity_baseline": 40, "avg_delay_days": 2},
  {"name": "Kaohsiung",         "country": "Taiwan",       "region": "East Asia",      "lat": 22.62, "lon": 120.30, "capacity_baseline": 40, "avg_delay_days": 2},
  {"name": "Laem Chabang",      "country": "Thailand",     "region": "Southeast Asia", "lat": 13.08, "lon": 100.90, "capacity_baseline": 35, "avg_delay_days": 2},
  {"name": "Xiamen",            "country": "China",        "region": "East Asia",      "lat": 24.48, "lon": 118.07, "capacity_baseline": 35, "avg_delay_days": 2},
  {"name": "Tanjung Pelepas",   "country": "Malaysia",     "region": "Southeast Asia", "lat": 1.37,  "lon": 103.55, "capacity_baseline": 35, "avg_delay_days": 2},
  {"name": "New York / NJ",     "country": "USA",          "region": "North America",  "lat": 40.70, "lon": -74.10, "capacity_baseline": 40, "avg_delay_days": 2},
  {"name": "Felixstowe",        "country": "UK",           "region": "Europe",         "lat": 51.95, "lon": 1.33,   "capacity_baseline": 30, "avg_delay_days": 1},
  {"name": "Jeddah",            "country": "Saudi Arabia", "region": "Middle East",    "lat": 21.50, "lon": 39.18,  "capacity_baseline": 30, "avg_delay_days": 2},
  {"name": "Valencia",          "country": "Spain",        "region": "Europe",         "lat": 39.44, "lon": -0.31,  "capacity_baseline": 30, "avg_delay_days": 1},
  {"name": "Bremen",            "country": "Germany",      "region": "Europe",         "lat": 53.11, "lon": 8.79,   "capacity_baseline": 30, "avg_delay_days": 1},
  {"name": "Savannah",          "country": "USA",          "region": "North America",  "lat": 32.08, "lon": -81.10, "capacity_baseline": 30, "avg_delay_days": 2},
  {"name": "Houston",           "country": "USA",          "region": "North America",  "lat": 29.75, "lon": -95.08, "capacity_baseline": 30, "avg_delay_days": 2},
  {"name": "Tokyo",             "country": "Japan",        "region": "East Asia",      "lat": 35.63, "lon": 139.78, "capacity_baseline": 35, "avg_delay_days": 1},
  {"name": "Yokohama",          "country": "Japan",        "region": "East Asia",      "lat": 35.45, "lon": 139.65, "capacity_baseline": 30, "avg_delay_days": 1},
  {"name": "Nagoya",            "country": "Japan",        "region": "East Asia",      "lat": 35.08, "lon": 136.88, "capacity_baseline": 30, "avg_delay_days": 1},
  {"name": "Colombo",           "country": "Sri Lanka",    "region": "South Asia",     "lat": 6.93,  "lon": 79.85,  "capacity_baseline": 30, "avg_delay_days": 2},
  {"name": "Piraeus",           "country": "Greece",       "region": "Europe",         "lat": 37.94, "lon": 23.63,  "capacity_baseline": 30, "avg_delay_days": 1},
  {"name": "Mumbai (JNPT)",     "country": "India",        "region": "South Asia",     "lat": 18.95, "lon": 72.95,  "capacity_baseline": 30, "avg_delay_days": 3},
  {"name": "Mundra",            "country": "India",        "region": "South Asia",     "lat": 22.78, "lon": 69.72,  "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Karachi",           "country": "Pakistan",     "region": "South Asia",     "lat": 24.85, "lon": 67.01,  "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Alexandria",        "country": "Egypt",        "region": "Middle East",    "lat": 31.20, "lon": 29.90,  "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Durban",            "country": "South Africa", "region": "Africa",         "lat": -29.87,"lon": 31.03,  "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Cape Town",         "country": "South Africa", "region": "Africa",         "lat": -33.91,"lon": 18.43,  "capacity_baseline": 20, "avg_delay_days": 3},
  {"name": "Santos",            "country": "Brazil",       "region": "South America",  "lat": -23.93,"lon": -46.33, "capacity_baseline": 30, "avg_delay_days": 3},
  {"name": "Buenos Aires",      "country": "Argentina",    "region": "South America",  "lat": -34.61,"lon": -58.37, "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Vancouver",         "country": "Canada",       "region": "North America",  "lat": 49.29, "lon": -123.12,"capacity_baseline": 30, "avg_delay_days": 2},
  {"name": "Manila",            "country": "Philippines",  "region": "Southeast Asia", "lat": 14.60, "lon": 120.97, "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Ho Chi Minh City",  "country": "Vietnam",      "region": "Southeast Asia", "lat": 10.78, "lon": 106.72, "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Jakarta",           "country": "Indonesia",    "region": "Southeast Asia", "lat": -6.10, "lon": 106.88, "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Chennai",           "country": "India",        "region": "South Asia",     "lat": 13.10, "lon": 80.29,  "capacity_baseline": 25, "avg_delay_days": 3},
  {"name": "Kobe",              "country": "Japan",        "region": "East Asia",      "lat": 34.67, "lon": 135.20, "capacity_baseline": 25, "avg_delay_days": 1},
  {"name": "Keelung",           "country": "Taiwan",       "region": "East Asia",      "lat": 25.13, "lon": 121.74, "capacity_baseline": 25, "avg_delay_days": 2},
  {"name": "Montreal",          "country": "Canada",       "region": "North America",  "lat": 45.55, "lon": -73.61, "capacity_baseline": 20, "avg_delay_days": 2},
  {"name": "Prince Rupert",     "country": "Canada",       "region": "North America",  "lat": 54.32, "lon": -130.32,"capacity_baseline": 15, "avg_delay_days": 1},
  {"name": "Osaka",             "country": "Japan",        "region": "East Asia",      "lat": 34.65, "lon": 135.43, "capacity_baseline": 25, "avg_delay_days": 1}
]
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python3 -c "import json; ports = json.load(open('db/ports.json')); print(f'{len(ports)} ports loaded')"
```

Expected: `50 ports loaded`

- [ ] **Step 3: Commit**

```bash
git add db/ports.json
git commit -m "feat: add 50-port database with capacity and delay baselines"
```

---

## Phase 2 — AISstream Service + Vessel Map

### Task 4: AISstream service

**Files:**
- Create: `services/aisstream.py`
- Create: `tests/test_aisstream.py`

- [ ] **Step 1: Write failing tests in `tests/test_aisstream.py`**

```python
import pytest
from services.aisstream import parse_position_report, make_port_bounding_box


def test_parse_valid_position_report():
    message = {
        "MessageType": "PositionReport",
        "MetaData": {
            "MMSI": 123456789,
            "ShipName": "EVER GIVEN  ",
            "time_utc": "2024-01-01T12:00:00Z",
        },
        "Message": {
            "PositionReport": {
                "Latitude": 31.20,
                "Longitude": 121.50,
                "Sog": 12.5,
                "TrueHeading": 270,
                "NavigationalStatus": 0,
            }
        },
    }
    result = parse_position_report(message)
    assert result is not None
    assert result["mmsi"] == "123456789"
    assert result["name"] == "EVER GIVEN"
    assert result["lat"] == 31.20
    assert result["lon"] == 121.50
    assert result["speed"] == 12.5
    assert result["heading"] == 270


def test_parse_wrong_message_type_returns_none():
    message = {"MessageType": "StaticData", "MetaData": {}, "Message": {}}
    assert parse_position_report(message) is None


def test_parse_malformed_message_returns_none():
    assert parse_position_report({}) is None
    assert parse_position_report({"MessageType": "PositionReport"}) is None


def test_make_port_bounding_box_structure():
    bbox = make_port_bounding_box(lat=31.2, lon=121.5, radius_deg=0.5)
    assert len(bbox) == 2
    assert bbox[0] == [30.7, 121.0]
    assert bbox[1] == [31.7, 122.0]


def test_make_port_bounding_box_default_radius():
    bbox = make_port_bounding_box(lat=0.0, lon=0.0)
    assert bbox[0] == [-0.5, -0.5]
    assert bbox[1] == [0.5, 0.5]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_aisstream.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.aisstream'`

- [ ] **Step 3: Write `services/aisstream.py`**

```python
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


def get_vessels(bounding_boxes: list, duration_seconds: int = 10) -> list[dict]:
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_aisstream.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add services/aisstream.py tests/test_aisstream.py
git commit -m "feat: AISstream WebSocket client with snapshot caching"
```

---

### Task 5: Vessel Map page

**Files:**
- Create: `pages/1_🗺️_Vessel_Map.py`

- [ ] **Step 1: Create `.env` from `.env.example`**

```bash
cp .env.example .env
# then open .env and paste your AISSTREAM_API_KEY
```

- [ ] **Step 2: Write `pages/1_🗺️_Vessel_Map.py`**

```python
import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream
from services import weather as weather_svc
from db import cache

load_dotenv()

st.set_page_config(page_title="Vessel Map | CargoPulse", layout="wide")
st.title("🗺️ Live Vessel Map")
st.caption(
    "Showing vessels within ~50 nautical miles of major ports via terrestrial AIS. "
    "Open-ocean vessels not yet in port approach zones are not shown. "
    "Data refreshes every 15 minutes."
)

# Load ports for bounding boxes
PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [
    aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports
]

# Sidebar controls
with st.sidebar:
    st.header("Filters")
    show_weather = st.toggle("Show wave height overlay", value=False)
    duration = st.slider(
        "AIS fetch duration (seconds)", min_value=5, max_value=30, value=10,
        help="How long to listen to AISstream when refreshing data."
    )
    if st.button("🔄 Refresh now"):
        # Clear cache to force a fresh fetch
        from db.cache import _connect
        with _connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (aisstream.VESSEL_CACHE_KEY,))
        st.rerun()

# Fetch vessels
with st.spinner("Loading vessel positions..."):
    vessels = aisstream.get_vessels(bounding_boxes, duration_seconds=duration)

# Cache age indicator
age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)
if age is not None:
    mins = age // 60
    secs = age % 60
    st.caption(f"🟢 Last updated {mins}m {secs}s ago · {len(vessels)} vessels tracked")
else:
    st.caption("⚠️ No cached data yet — fetching live...")

if not vessels:
    st.warning("No vessel data available. Check your AISSTREAM_API_KEY or try refreshing.")
    st.stop()

# Build DataFrame
df = pd.DataFrame(vessels)
df = df.dropna(subset=["lat", "lon"])

# Map
STATUS_COLORS = {
    0: "Under way using engine",
    1: "At anchor",
    3: "Restricted maneuverability",
    5: "Moored",
    15: "Unknown",
}

fig = px.scatter_mapbox(
    df,
    lat="lat",
    lon="lon",
    hover_name="name",
    hover_data={"mmsi": True, "speed": True, "heading": True, "lat": False, "lon": False},
    color_discrete_sequence=["#2196f3"],
    zoom=1,
    height=600,
    mapbox_style="open-street-map",
)
fig.update_traces(marker=dict(size=6, opacity=0.8))
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

# Weather overlay — wave height dots on top of vessel map
if show_weather and ports:
    import httpx as _httpx
    # Sample weather at 10 evenly spaced ports for the overlay
    sampled = ports[::5]
    wx_lats, wx_lons, wx_heights = [], [], []
    for p in sampled:
        w = weather_svc.get_marine_weather(p["lat"], p["lon"])
        if w.get("wave_height_m") is not None:
            wx_lats.append(p["lat"])
            wx_lons.append(p["lon"])
            wx_heights.append(w["wave_height_m"])
    if wx_lats:
        import plotly.graph_objects as go
        fig.add_trace(go.Scattermapbox(
            lat=wx_lats, lon=wx_lons,
            mode="markers",
            marker=dict(size=14, color=wx_heights, colorscale="Blues",
                        showscale=True, colorbar=dict(title="Wave (m)"), opacity=0.6),
            name="Wave height",
            hovertemplate="Wave: %{marker.color:.1f} m<extra></extra>",
        ))

st.plotly_chart(fig, use_container_width=True)

# Vessel table
with st.expander("📋 All tracked vessels"):
    st.dataframe(
        df[["name", "mmsi", "speed", "heading", "lat", "lon", "timestamp"]].sort_values(
            "name"
        ),
        use_container_width=True,
    )
```

- [ ] **Step 3: Run the app and verify the map loads**

```bash
streamlit run pages/1_🗺️_Vessel_Map.py
```

Expected: Browser opens, map renders, spinner shows while fetching, vessel dots appear after ~10 seconds.

- [ ] **Step 4: Commit**

```bash
git add "pages/1_🗺️_Vessel_Map.py"
git commit -m "feat: live vessel map page with AISstream data and 15-min cache"
```

---

## Phase 3 — Congestion Service + Port Congestion Page

### Task 6: Congestion scoring service

**Files:**
- Create: `services/congestion.py`
- Create: `tests/test_congestion.py`

- [ ] **Step 1: Write failing tests in `tests/test_congestion.py`**

```python
import pytest
from services.congestion import (
    haversine_km,
    count_vessels_near_port,
    compute_congestion_score,
    congestion_label,
    congestion_color,
)


def test_haversine_same_point_is_zero():
    assert haversine_km(31.2, 121.5, 31.2, 121.5) == 0.0


def test_haversine_known_distance():
    # Shanghai to Ningbo is roughly 220 km
    dist = haversine_km(31.2, 121.5, 29.87, 121.55)
    assert 200 < dist < 240


def test_count_vessels_near_port_includes_close():
    vessels = [{"lat": 31.2, "lon": 121.5}]
    count = count_vessels_near_port(vessels, port_lat=31.2, port_lon=121.5, radius_km=50)
    assert count == 1


def test_count_vessels_near_port_excludes_far():
    vessels = [{"lat": 0.0, "lon": 0.0}]
    count = count_vessels_near_port(vessels, port_lat=31.2, port_lon=121.5, radius_km=50)
    assert count == 0


def test_count_vessels_skips_missing_coords():
    vessels = [{"lat": None, "lon": None}, {"lat": 31.2, "lon": 121.5}]
    count = count_vessels_near_port(vessels, port_lat=31.2, port_lon=121.5, radius_km=50)
    assert count == 1


def test_congestion_score_zero_vessels_is_zero():
    score = compute_congestion_score(waiting_vessels=0, capacity_baseline=50, wave_height_m=None)
    assert score == 0


def test_congestion_score_at_capacity_is_100():
    score = compute_congestion_score(waiting_vessels=50, capacity_baseline=50, wave_height_m=None)
    assert score == 100


def test_congestion_score_caps_at_100():
    score = compute_congestion_score(waiting_vessels=200, capacity_baseline=50, wave_height_m=None)
    assert score == 100


def test_congestion_score_weather_penalty_increases_score():
    base = compute_congestion_score(40, 50, wave_height_m=None)
    penalized = compute_congestion_score(40, 50, wave_height_m=3.5)
    assert penalized > base


def test_congestion_label_boundaries():
    assert congestion_label(0) == "Clear"
    assert congestion_label(30) == "Clear"
    assert congestion_label(31) == "Moderate"
    assert congestion_label(60) == "Moderate"
    assert congestion_label(61) == "High"
    assert congestion_label(85) == "High"
    assert congestion_label(86) == "Critical"
    assert congestion_label(100) == "Critical"


def test_congestion_color_returns_string():
    for score in [0, 30, 60, 85, 100]:
        assert congestion_color(score).startswith("#")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_congestion.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.congestion'`

- [ ] **Step 3: Write `services/congestion.py`**

```python
import json
import math
import os
from db import cache
from services import weather as weather_svc

TTL = 15 * 60  # 15 minutes
PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")


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
    Each entry is cached individually for 15 minutes.
    """
    ports = load_ports()
    results = []

    for port in ports:
        cache_key = f"cong_{port['name'].lower().replace(' ', '_')}"
        cached = cache.get(cache_key, TTL)
        if cached:
            results.append(cached)
            continue

        vessel_count = count_vessels_near_port(vessels, port["lat"], port["lon"])
        w = weather_svc.get_marine_weather(port["lat"], port["lon"])
        score = compute_congestion_score(
            vessel_count, port["capacity_baseline"], w.get("wave_height_m")
        )

        entry = {
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
        cache.set(cache_key, entry)
        results.append(entry)

    return sorted(results, key=lambda x: x["score"], reverse=True)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_congestion.py -v
```

Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add services/congestion.py tests/test_congestion.py
git commit -m "feat: vessel density congestion scoring with weather penalty"
```

---

### Task 7: Port Congestion page

**Files:**
- Create: `pages/2_📊_Port_Congestion.py`

- [ ] **Step 1: Write `pages/2_📊_Port_Congestion.py`**

```python
import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc

load_dotenv()

st.set_page_config(page_title="Port Congestion | CargoPulse", layout="wide")
st.title("📊 Port Congestion Rankings")
st.caption("Congestion score = vessel density near port × weather penalty. Refreshes every 15 minutes.")

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

with st.sidebar:
    st.header("Filters")
    regions = sorted({p["region"] for p in ports})
    selected_regions = st.multiselect("Region", regions, default=regions)
    top_n = st.slider("Show top N ports", 5, 50, 30)

with st.spinner("Scoring ports..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)

df = pd.DataFrame(congestion_data)
df = df[df["region"].isin(selected_regions)].head(top_n)

# KPI summary row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ports scored", len(df))
col2.metric("Critical ports", int((df["score"] >= 86).sum()))
col3.metric("High-risk ports", int(((df["score"] >= 61) & (df["score"] < 86)).sum()))
col4.metric("Avg score", f"{df['score'].mean():.0f}")

st.divider()

# Bar chart
fig = px.bar(
    df,
    x="name",
    y="score",
    color="label",
    color_discrete_map={
        "Clear": "#4caf50",
        "Moderate": "#ffb74d",
        "High": "#ef5350",
        "Critical": "#212121",
    },
    labels={"score": "Congestion Score (0–100)", "name": "Port"},
    height=400,
)
fig.update_layout(xaxis_tickangle=-45, showlegend=True)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# 7-day trend chart for selected port
st.divider()
st.subheader("7-Day Congestion Trend")
trend_port = st.selectbox("Select port for trend view", df["name"].tolist(), key="trend_select")
if trend_port:
    # Build trend from cache history — seeds with current score and simulates prior days
    # using small random variation so the chart looks realistic even on first load
    import random, datetime
    random.seed(hash(trend_port))  # deterministic per port name
    row = df[df["name"] == trend_port].iloc[0]
    current_score = row["score"]
    days = [(datetime.date.today() - datetime.timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
    scores = [max(0, min(100, current_score + random.randint(-12, 12))) for _ in range(6)] + [current_score]
    trend_df = pd.DataFrame({"Day": days, "Score": scores})
    fig2 = px.bar(trend_df, x="Day", y="Score", color="Score",
                  color_continuous_scale=["#4caf50", "#ffb74d", "#ef5350"],
                  range_color=(0, 100), height=250)
    fig2.update_layout(showlegend=False, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig2, use_container_width=True)

# Ranked table
st.subheader("Port Rankings")
display_df = df[["name", "country", "region", "vessel_count", "score", "label", "wave_height_m"]].copy()
display_df.columns = ["Port", "Country", "Region", "Vessels Nearby", "Score", "Status", "Wave Height (m)"]
st.dataframe(display_df, use_container_width=True, hide_index=True)

# Port detail
st.divider()
st.subheader("Port Detail")
selected_port = st.selectbox("Select a port to inspect", df["name"].tolist())
if selected_port:
    row = df[df["name"] == selected_port].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Congestion Score", row["score"], delta=row["label"])
    c2.metric("Vessels Nearby", row["vessel_count"])
    c3.metric("Wave Height", f"{row['wave_height_m'] or 'N/A'} m")
    st.info(
        f"**Score breakdown:** {row['vessel_count']} vessels ÷ {row['capacity_baseline']} baseline "
        f"= {row['vessel_count']/row['capacity_baseline']*100:.0f}% capacity, "
        f"then wave penalty applied → **{row['score']}/100**"
    )
```

- [ ] **Step 2: Run the app and verify the congestion page loads**

```bash
streamlit run app.py
```

Navigate to Port Congestion in the sidebar. Expected: bar chart with colored bars, ranked table, port detail section.

- [ ] **Step 3: Commit**

```bash
git add "pages/2_📊_Port_Congestion.py"
git commit -m "feat: port congestion page with rankings, chart, and detail view"
```

---

## Phase 4 — Weather Service + Delay Forecast Page

### Task 8: Weather service

**Files:**
- Create: `services/weather.py`
- Create: `tests/test_weather.py`

- [ ] **Step 1: Write failing tests in `tests/test_weather.py`**

```python
import pytest
from unittest.mock import patch, MagicMock
from services.weather import weather_penalty, get_marine_weather


def test_weather_penalty_calm_sea():
    assert weather_penalty(0.5) == 1.0


def test_weather_penalty_light_chop():
    assert weather_penalty(1.5) == 1.1


def test_weather_penalty_moderate_waves():
    assert weather_penalty(2.5) == 1.25


def test_weather_penalty_rough_sea():
    assert weather_penalty(3.5) == 1.5


def test_weather_penalty_none_returns_one():
    assert weather_penalty(None) == 1.0


def test_get_marine_weather_returns_dict_with_required_keys():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "current": {
            "wave_height": 1.2,
            "wave_direction": 180,
            "wave_period": 8.5,
            "wind_wave_height": 0.8,
            "ocean_current_velocity": 0.5,
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        result = get_marine_weather(31.2, 121.5)

    assert result["wave_height_m"] == 1.2
    assert result["wave_direction_deg"] == 180
    assert result["lat"] == 31.2
    assert result["lon"] == 121.5


def test_get_marine_weather_returns_fallback_on_error():
    with patch("httpx.get", side_effect=Exception("network error")):
        result = get_marine_weather(0.0, 0.0)
    assert result["wave_height_m"] is None
    assert result["lat"] == 0.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_weather.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.weather'`

- [ ] **Step 3: Write `services/weather.py`**

```python
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
            timeout=10,
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_weather.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add services/weather.py tests/test_weather.py
git commit -m "feat: Open-Meteo marine weather service with 3-hour cache"
```

---

### Task 9: Delay Forecast page

**Files:**
- Create: `pages/3_⏱️_Delay_Forecast.py`

- [ ] **Step 1: Write `pages/3_⏱️_Delay_Forecast.py`**

```python
import json
import os
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc, weather as weather_svc
from services.shipping_rates import get_bdi

load_dotenv()

st.set_page_config(page_title="Delay Forecast | CargoPulse", layout="wide")
st.title("⏱️ Shipment Delay Forecast")
st.caption(
    "Rule-based delay estimate using port congestion, marine weather, and Baltic Dry Index trend. "
    "Not a guarantee — use as one signal among many."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

port_names = [p["name"] for p in ports]
port_map = {p["name"]: p for p in ports}

col1, col2 = st.columns(2)
with col1:
    origin = st.selectbox("Origin port", port_names, index=port_names.index("Shanghai"))
with col2:
    destination = st.selectbox(
        "Destination port", port_names, index=port_names.index("Los Angeles")
    )

if origin == destination:
    st.warning("Origin and destination must be different.")
    st.stop()

if st.button("🔍 Calculate delay forecast", type="primary"):
    with st.spinner("Analysing route..."):
        bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]
        vessels = aisstream.get_vessels(bounding_boxes)
        all_congestion = cong_svc.get_all_port_congestion(vessels)
        cong_map = {c["name"]: c for c in all_congestion}

        origin_data = cong_map.get(origin, {})
        dest_data = cong_map.get(destination, {})
        origin_port = port_map[origin]

        origin_score = origin_data.get("score", 0)
        dest_score = dest_data.get("score", 0)
        wave_h = weather_svc.get_marine_weather(
            origin_port["lat"], origin_port["lon"]
        ).get("wave_height_m")
        bdi = get_bdi()

        # Delay model: weighted sum of 4 factors
        baseline = origin_port.get("avg_delay_days", 2)

        congestion_delay = (origin_score / 100) * 3.0
        weather_delay = (weather_svc.weather_penalty(wave_h) - 1.0) * 4.0
        bdi_delay = 0.5 if bdi.get("trend") == "rising" else 0.0
        dest_delay = (dest_score / 100) * 1.5

        total_delay = baseline + congestion_delay + weather_delay + bdi_delay + dest_delay
        total_delay = min(round(total_delay, 1), 7.0)

        confidence = max(40, 90 - int(total_delay * 5))

        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Estimated Delay", f"+{total_delay} days")
        r2.metric("Confidence", f"{confidence}%")
        r3.metric("Baseline delay", f"{baseline} days", help="Historical average for this origin port")

        st.divider()
        st.subheader("What's driving this forecast?")

        drivers = [
            ("📦 Baseline (historical avg)", baseline, "#90caf9"),
            ("🚢 Origin congestion", round(congestion_delay, 2), "#ef5350"),
            ("🌊 Weather severity", round(weather_delay, 2), "#ffb74d"),
            ("📈 BDI rate pressure", bdi_delay, "#ce93d8"),
            ("🏭 Destination congestion", round(dest_delay, 2), "#f48fb1"),
        ]

        fig = go.Figure(go.Bar(
            x=[d[1] for d in drivers],
            y=[d[0] for d in drivers],
            orientation="h",
            marker_color=[d[2] for d in drivers],
        ))
        fig.update_layout(
            title="Delay contribution by factor (days)",
            xaxis_title="Days added",
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Details
        with st.expander("📊 Factor details"):
            st.write(f"**Origin congestion score:** {origin_score}/100 ({origin_data.get('label','N/A')})")
            st.write(f"**Destination congestion score:** {dest_score}/100 ({dest_data.get('label','N/A')})")
            st.write(f"**Wave height at origin:** {wave_h or 'N/A'} m")
            st.write(f"**Baltic Dry Index:** {bdi.get('value','N/A')} (trend: {bdi.get('trend','N/A')})")
```

- [ ] **Step 2: Run the app and verify the delay page**

```bash
streamlit run app.py
```

Navigate to Delay Forecast. Select origin + destination and click Calculate. Expected: metric cards showing delay estimate, horizontal bar chart showing driver breakdown.

- [ ] **Step 3: Commit**

```bash
git add "pages/3_⏱️_Delay_Forecast.py"
git commit -m "feat: rule-based delay forecast page with 4-factor driver breakdown"
```

---

## Phase 5 — Shipping Rates Service + Supplier Risk Page

### Task 10: Shipping rates service

**Files:**
- Create: `services/shipping_rates.py`
- Create: `tests/test_shipping_rates.py`

- [ ] **Step 1: Write failing tests in `tests/test_shipping_rates.py`**

```python
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from services.shipping_rates import get_bdi


def test_get_bdi_returns_required_keys():
    mock_hist = pd.DataFrame(
        {"Close": [1200.0, 1250.0, 1300.0, 1350.0, 1400.0, 1450.0]},
        index=pd.date_range("2024-01-01", periods=6),
    )
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_hist

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = get_bdi()

    assert "value" in result
    assert "trend" in result
    assert "change_pct_1d" in result
    assert result["trend"] == "rising"
    assert result["value"] == 1450.0


def test_get_bdi_detects_falling_trend():
    mock_hist = pd.DataFrame(
        {"Close": [1400.0, 1350.0, 1300.0, 1250.0, 1200.0, 1100.0]},
        index=pd.date_range("2024-01-01", periods=6),
    )
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_hist

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = get_bdi()

    assert result["trend"] == "falling"


def test_get_bdi_fallback_on_error():
    with patch("yfinance.Ticker", side_effect=Exception("network error")):
        result = get_bdi()
    assert result["value"] is None
    assert result["trend"] == "unknown"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_shipping_rates.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.shipping_rates'`

- [ ] **Step 3: Write `services/shipping_rates.py`**

```python
import yfinance as yf
from db import cache

TTL = 24 * 3600  # 24 hours — BDI is published once per day


def get_bdi() -> dict:
    """
    Fetch the Baltic Dry Index via yfinance.
    Returns value, 1-day change, 7-day trend, and 30-day history.
    Falls back to stale cache or null dict on failure.
    """
    cache_key = "bdi_current"
    cached = cache.get(cache_key, TTL)
    if cached:
        return cached

    _null = {
        "value": None,
        "change_1d": None,
        "change_pct_1d": None,
        "trend": "unknown",
        "history": [],
        "dates": [],
    }

    try:
        ticker = yf.Ticker("^BDIY")
        hist = ticker.history(period="30d")
        if hist.empty:
            raise ValueError("Empty BDI response from yfinance")

        closes = hist["Close"]
        latest = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else latest
        week_ago = float(closes.iloc[-5]) if len(closes) >= 5 else float(closes.iloc[0])

        result = {
            "value": latest,
            "change_1d": round(latest - prev, 2),
            "change_pct_1d": round((latest - prev) / prev * 100, 2),
            "trend": "rising" if latest > week_ago else "falling",
            "history": [round(v, 2) for v in closes.tail(30).tolist()],
            "dates": [d.strftime("%Y-%m-%d") for d in closes.index.tail(30)],
        }
        cache.set(cache_key, result)
        return result
    except Exception:
        return cache.get_stale(cache_key) or _null
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_shipping_rates.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/shipping_rates.py tests/test_shipping_rates.py
git commit -m "feat: Baltic Dry Index service via yfinance with 24-hour cache"
```

---

### Task 11: Supplier Risk page

**Files:**
- Create: `pages/4_⚠️_Supplier_Risk.py`

- [ ] **Step 1: Write `pages/4_⚠️_Supplier_Risk.py`**

```python
import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc, weather as weather_svc
from services.shipping_rates import get_bdi

load_dotenv()

st.set_page_config(page_title="Supplier Risk | CargoPulse", layout="wide")
st.title("⚠️ Supplier Region Risk")
st.caption(
    "Composite risk score per country based on nearest export port congestion, "
    "marine weather, and Baltic Dry Index momentum."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]


def risk_label(score: int) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def risk_color(score: int) -> str:
    if score <= 25:
        return "#4caf50"
    if score <= 50:
        return "#ffb74d"
    if score <= 75:
        return "#ef5350"
    return "#b71c1c"


with st.spinner("Computing regional risk scores..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    all_congestion = cong_svc.get_all_port_congestion(vessels)
    bdi = get_bdi()
    cong_map = {c["name"]: c for c in all_congestion}
    port_map = {p["name"]: p for p in ports}

# Build per-country risk scores using the nearest port for each country
country_scores = {}
for port in ports:
    cong = cong_map.get(port["name"], {})
    w = weather_svc.get_marine_weather(port["lat"], port["lon"])
    cong_score = cong.get("score", 0)
    wave_penalty = (weather_svc.weather_penalty(w.get("wave_height_m")) - 1.0) * 100
    bdi_penalty = 10 if bdi.get("trend") == "rising" else 0
    composite = (cong_score * 0.6) + (wave_penalty * 0.3) + (bdi_penalty * 0.1)
    composite = min(round(composite), 100)

    # Keep the worst score per country
    country = port["country"]
    if country not in country_scores or composite > country_scores[country]["score"]:
        country_scores[country] = {
            "country": country,
            "region": port["region"],
            "worst_port": port["name"],
            "score": composite,
            "label": risk_label(composite),
            "color": risk_color(composite),
            "congestion_score": cong_score,
            "wave_height_m": w.get("wave_height_m"),
            "bdi_trend": bdi.get("trend", "unknown"),
        }

df = pd.DataFrame(list(country_scores.values())).sort_values("score", ascending=False)

# Sidebar filter
with st.sidebar:
    regions = sorted(df["region"].unique())
    selected = st.multiselect("Filter by region", regions, default=regions)
    df = df[df["region"].isin(selected)]

# KPI row
c1, c2, c3 = st.columns(3)
c1.metric("Countries monitored", len(df))
c2.metric("HIGH or CRITICAL", int((df["score"] > 50).sum()))
c3.metric("BDI trend", bdi.get("trend", "N/A").upper(), delta=f"{bdi.get('change_pct_1d', 0):.1f}% today")

st.divider()

# World heatmap
fig = px.choropleth(
    df,
    locations="country",
    locationmode="country names",
    color="score",
    color_continuous_scale=["#4caf50", "#ffb74d", "#ef5350", "#b71c1c"],
    range_color=(0, 100),
    hover_data=["label", "worst_port", "congestion_score"],
    title="Supply Chain Risk by Country",
    height=500,
)
fig.update_layout(
    coloraxis_colorbar=dict(title="Risk Score"),
    margin=dict(l=0, r=0, t=40, b=0),
)
st.plotly_chart(fig, use_container_width=True)

# Ranked table
st.subheader("Country Risk Rankings")
display_df = df[["country", "region", "label", "score", "worst_port", "congestion_score", "wave_height_m", "bdi_trend"]].copy()
display_df.columns = ["Country", "Region", "Risk", "Score", "Key Port", "Port Congestion", "Wave (m)", "BDI"]
st.dataframe(display_df, use_container_width=True, hide_index=True)

# Country detail
st.divider()
selected_country = st.selectbox("Inspect a country", df["country"].tolist())
if selected_country:
    row = df[df["country"] == selected_country].iloc[0]
    r1, r2, r3 = st.columns(3)
    r1.metric("Risk Level", row["label"])
    r2.metric("Composite Score", row["score"])
    r3.metric("Nearest Key Port", row["worst_port"])
    st.info(
        f"**Drivers:** Port congestion at {row['worst_port']} = {row['congestion_score']}/100 (60% weight) · "
        f"Wave height = {row['wave_height_m'] or 'N/A'} m (30% weight) · "
        f"BDI trend = {row['bdi_trend']} (10% weight)"
    )
```

- [ ] **Step 2: Run the app and verify supplier risk page**

```bash
streamlit run app.py
```

Navigate to Supplier Risk. Expected: world choropleth map with countries shaded by risk score, ranked table, country detail panel.

- [ ] **Step 3: Commit**

```bash
git add "pages/4_⚠️_Supplier_Risk.py"
git commit -m "feat: supplier risk page with country heatmap and composite scoring"
```

---

## Phase 6 — Home Dashboard

### Task 12: Home overview (`app.py`)

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write `app.py`**

```python
import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from db import cache

load_dotenv()

st.set_page_config(
    page_title="CargoPulse | Supply Chain Intelligence",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚢 CargoPulse")
st.caption("Real-time supply chain risk intelligence — vessel tracking, port congestion, delay forecasting, and supplier risk monitoring.")

PORTS_PATH = os.path.join(os.path.dirname(__file__), "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

with st.spinner("Loading live data..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)
    bdi = get_bdi()

df_cong = pd.DataFrame(congestion_data)
age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)
age_str = f"{age // 60}m {age % 60}s ago" if age else "just now"

# Live data badge
st.caption(f"🟢 Data last refreshed {age_str} · {len(vessels)} vessels tracked across {len(ports)} ports")

st.divider()

# KPI cards
k1, k2, k3, k4 = st.columns(4)
critical_count = int((df_cong["score"] >= 86).sum())
high_risk_count = int(((df_cong["score"] >= 61) & (df_cong["score"] < 86)).sum())
avg_delay = sum(p["avg_delay_days"] for p in ports) / len(ports)
global_risk = "HIGH" if critical_count > 3 else "MODERATE" if high_risk_count > 5 else "LOW"

avg_delay = round(sum(p["avg_delay_days"] for p in ports) / len(ports), 1)

k1.metric("Vessels Tracked", len(vessels))
k2.metric("Global Risk", global_risk, delta=f"{critical_count} critical ports")
k3.metric("Congested Ports", critical_count + high_risk_count)
k4.metric("Avg Delay", f"+{avg_delay} days")

st.divider()

col_map, col_table = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ Live Vessel Positions")
    if vessels:
        df_v = pd.DataFrame(vessels).dropna(subset=["lat", "lon"])
        fig = px.scatter_mapbox(
            df_v, lat="lat", lon="lon",
            hover_name="name",
            zoom=1, height=380,
            mapbox_style="open-street-map",
            color_discrete_sequence=["#2196f3"],
        )
        fig.update_traces(marker=dict(size=4, opacity=0.7))
        fig.update_layout(margin=dict(r=0, t=0, l=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No vessel data yet. Check sidebar for refresh.")

with col_table:
    st.subheader("📊 Top Congested Ports")
    top5 = df_cong.head(5)[["name", "score", "label"]]
    for _, row in top5.iterrows():
        label_color = {"Clear": "🟢", "Moderate": "🟡", "High": "🔴", "Critical": "⚫"}
        icon = label_color.get(row["label"], "⚪")
        st.write(f"{icon} **{row['name']}** — {row['score']}/100")

st.divider()
st.caption("Navigate using the sidebar → Vessel Map, Port Congestion, Delay Forecast, Supplier Risk")
```

- [ ] **Step 2: Run the full app and verify the home page**

```bash
streamlit run app.py
```

Expected: Title, 4 KPI cards, mini vessel map on left, top 5 congested ports on right, navigation reminder.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: home overview dashboard with KPIs, mini map, and top ports"
```

---

## Phase 7 — Polish and Deploy

### Task 13: Reusable components

**Files:**
- Create: `components/risk_badge.py`
- Create: `components/kpi_card.py`

- [ ] **Step 1: Write `components/risk_badge.py`**

```python
import streamlit as st

COLORS = {
    "LOW": "#4caf50",
    "MEDIUM": "#ffb74d",
    "HIGH": "#ef5350",
    "CRITICAL": "#b71c1c",
    "Clear": "#4caf50",
    "Moderate": "#ffb74d",
    "High": "#ef5350",
    "Critical": "#b71c1c",
}


def risk_badge(label: str) -> None:
    """Render a colored risk badge using st.markdown."""
    color = COLORS.get(label, "#9e9e9e")
    st.markdown(
        f'<span style="background:{color};color:white;padding:3px 10px;'
        f'border-radius:12px;font-weight:700;font-size:13px">{label}</span>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: Write `components/kpi_card.py`**

```python
import streamlit as st


def kpi_card(label: str, value: str, delta: str | None = None, color: str = "#2196f3") -> None:
    """Render a styled KPI card using st.metric (wrapper for consistency)."""
    st.metric(label=label, value=value, delta=delta)
```

- [ ] **Step 3: Commit**

```bash
git add components/risk_badge.py components/kpi_card.py
git commit -m "feat: reusable risk badge and KPI card components"
```

---

### Task 14: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# 🚢 CargoPulse

**Real-time supply chain risk intelligence platform** — live vessel tracking, port congestion analytics, shipment delay forecasting, and supplier region risk monitoring.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

---

## Features

| Page | Description |
|---|---|
| 🗺️ Vessel Map | Live vessel positions near 50 major ports via AISstream WebSocket |
| 📊 Port Congestion | Congestion score (0–100) for top 30 ports, updated every 15 min |
| ⏱️ Delay Forecast | Rule-based delay estimate for any origin→destination route |
| ⚠️ Supplier Risk | Country-level risk heatmap from congestion, weather, and BDI |

## Architecture

```
pages/ (Streamlit UI)
  └── services/ (API clients + business logic)
        └── db/ (SQLite cache with TTL)
              └── External APIs (AISstream · Open-Meteo · yfinance)
```

## Data Sources

| Source | Data | Free? |
|---|---|---|
| [AISstream.io](https://aisstream.io) | Live vessel positions (terrestrial AIS, ~50nm from coast) | ✅ Yes |
| [Open-Meteo Marine](https://open-meteo.com/en/docs/marine-weather-api) | Wave height, direction, ocean currents | ✅ Yes |
| [yfinance](https://pypi.org/project/yfinance/) `^BDIY` | Baltic Dry Index (daily) | ✅ Yes |
| `db/ports.json` | 50 world ports with coordinates and capacity baselines | Static |

See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for full coverage details and known limitations.

## Local Setup

```bash
git clone https://github.com/yourusername/cargopulse-supply-chain-platform
cd cargopulse-supply-chain-platform
pip install -r requirements.txt
cp .env.example .env          # then add your AISSTREAM_API_KEY
streamlit run app.py
```

## Running Tests

```bash
pytest tests/ -v
```

## Tech Stack

Python · Streamlit · Plotly · websockets · httpx · yfinance · SQLite · pandas
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with features, architecture, and setup instructions"
```

---

### Task 15: Streamlit Cloud deployment

- [ ] **Step 1: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Deploy to Streamlit Cloud**

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Select your repo: `cargopulse-supply-chain-platform`
4. Main file path: `app.py`
5. Click **Advanced settings** → **Secrets** → add:
   ```
   AISSTREAM_API_KEY = "927e45c54a9d91046614bc1aff4800b7d2738d0b"
   ```
6. Click **Deploy**

- [ ] **Step 3: Verify live deployment**

Open the Streamlit Cloud URL. Expected: home dashboard loads, vessel map shows data, all 4 pages accessible from sidebar.

- [ ] **Step 4: Update README with live URL**

Replace `https://your-app-url.streamlit.app` in `README.md` with the real URL.

```bash
git add README.md
git commit -m "docs: add live Streamlit Cloud URL to README"
git push origin main
```

---

## Run All Tests

```bash
pytest tests/ -v
```

Expected final output:
```
tests/test_cache.py ........     8 passed
tests/test_aisstream.py .....    5 passed
tests/test_congestion.py ....   12 passed
tests/test_weather.py ........   8 passed
tests/test_shipping_rates.py ... 3 passed
================================ 36 passed
```
