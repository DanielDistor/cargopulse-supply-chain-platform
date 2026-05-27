# CargoPulse — Design Spec
**Date:** 2026-05-27
**Status:** Approved

---

## Overview

CargoPulse is a real-time supply chain risk intelligence platform built as a portfolio project targeting supply chain, operations, and logistics engineering roles (Tesla, Amazon Ops, Apple Supply Chain, semiconductor/manufacturing companies).

**Resume line:**
> Built CargoPulse, a real-time logistics visibility and risk intelligence platform integrating live vessel tracking, congestion analytics, delay forecasting, and supplier risk monitoring.

**Primary goal:** Impress recruiters with an enterprise-grade, live-data dashboard deployed at a public URL.

**Deployment:** Streamlit Cloud (free) + polished GitHub repo with README.

---

## Architecture — Layered (Option B)

Single Streamlit application. No separate backend server. Four clean layers:

```
┌─────────────────────────────────────────┐
│           PRESENTATION LAYER            │
│   pages/ + components/                  │
└──────────────┬──────────────────────────┘
               │ calls
┌──────────────▼──────────────────────────┐
│             SERVICE LAYER               │
│   services/ — API calls + business logic│
└──────────────┬──────────────────────────┘
               │ reads/writes
┌──────────────▼──────────────────────────┐
│              CACHE LAYER                │
│   db/ — SQLite with TTL-based caching   │
└──────────────┬──────────────────────────┘
               │ connects to
┌──────────────▼──────────────────────────┐
│            EXTERNAL APIS                │
│   AISstream · Open-Meteo · yfinance     │
└─────────────────────────────────────────┘
```

**Why this architecture:**
- One process, one deployment, one free Streamlit Cloud app
- Each layer has a single responsibility — easy to build, test, and extend
- Services can be swapped independently (e.g., upgrade from terrestrial to satellite AIS) without touching pages

---

## Folder Structure

```
cargopulse-supply-chain-platform/
├── app.py                        ← Home overview dashboard
├── pages/
│   ├── 1_🗺️_Vessel_Map.py
│   ├── 2_📊_Port_Congestion.py
│   ├── 3_⏱️_Delay_Forecast.py
│   └── 4_⚠️_Supplier_Risk.py
├── services/
│   ├── aisstream.py              ← AISstream WebSocket client
│   ├── weather.py                ← Open-Meteo REST calls
│   ├── shipping_rates.py         ← yfinance BDI fetch
│   └── congestion.py             ← Vessel density → congestion score
├── db/
│   ├── cache.py                  ← SQLite helpers + TTL logic
│   ├── cache.db                  ← Auto-created (gitignored)
│   └── ports.json                ← Top 50 world ports (lat/lon/country)
├── components/
│   ├── risk_badge.py
│   ├── vessel_card.py
│   └── port_card.py
├── docs/
│   └── DATA_SOURCES.md           ← API sources + known limitations
├── .env                          ← API keys (gitignored)
├── .env.example                  ← Key template
├── requirements.txt
└── README.md
```

---

## Data Sources

| Layer | Source | Refresh | Key |
|---|---|---|---|
| Vessel positions | AISstream.io WebSocket | Real-time (~seconds) | Yes |
| Marine weather | Open-Meteo Marine API | Every 1–6 hours | No |
| Port congestion score | Computed from vessel density | Same as AISstream | No |
| Shipping rates (BDI) | yfinance `^BDIY` | Daily | No |
| Port coordinates | Static `ports.json` | Never | No |

**Only one API key required: `AISSTREAM_API_KEY`**

See `docs/DATA_SOURCES.md` for full limitations disclosure including terrestrial AIS coverage range (~50 nautical miles from coastlines).

---

## Feature Pages

### 🏠 Home — Overview Dashboard (`app.py`)
- 4 KPI cards: Vessels Tracked / Global Risk Level / Congested Ports Count / Avg Delay
- Mini vessel map preview (non-interactive)
- Top 5 congested ports list
- Live data status indicator

### 🗺️ Page 1 — Vessel Map
- Plotly `scatter_mapbox` with live vessel positions
- Dots color-coded by vessel type (container / tanker / bulk carrier)
- Click vessel → side panel with name, flag, speed, heading, destination
- Wave height overlay toggle (Open-Meteo)
- UI note: "Showing vessels within ~50nm of coastlines via terrestrial AIS"

### 📊 Page 2 — Port Congestion
- Top 30 ports ranked by congestion score (0–100)
- Score formula: `(waiting_vessels / capacity_baseline) × weather_penalty`
  - `capacity_baseline` = typical vessel count per port, stored in `ports.json`
  - `weather_penalty` = multiplier 1.0–1.5 derived from wave height + wind speed from Open-Meteo
- Color coding: 🟢 Clear (0–30) / 🟡 Moderate (31–60) / 🔴 High (61–85) / ⚫ Critical (86–100)
- 7-day trend bar chart per selected port
- Click port → detail: vessel count, avg wait time, weather, score breakdown

### ⏱️ Page 3 — Delay Forecast
- Inputs: origin port + destination port (dropdowns from `ports.json`)
- Output: estimated delay `+0` to `+7 days` with confidence percentage
- Model: rule-based weighted score using congestion + weather severity + BDI trend + hardcoded baseline delay per trade route (stored in `ports.json` as `avg_delay_days`)
- Driver breakdown: top 3 factors contributing to the delay estimate
- No ML — transparent, explainable, and fast

### ⚠️ Page 4 — Supplier Risk
- Input: country or region selector
- Composite risk score from: congestion at nearest export port + weather severity + BDI momentum
- Risk levels: LOW / MEDIUM / HIGH / CRITICAL with color-coded badge
- Plotly choropleth world heatmap shaded by risk level
- Plain-English breakdown: "Top 3 factors driving this risk"

---

## Data Flow

```
User loads page
     │
     ▼
Page calls service function
     │
     ▼
Cache layer checks SQLite
     ├── Data fresh? → Return cached data instantly
     └── Stale/missing? → Call API → Cache result → Return data
     │
     ▼
Service returns clean dict/dataframe
     │
     ▼
Page renders Plotly chart / table / map
```

**Cache TTLs:**

| Source | TTL | Reason |
|---|---|---|
| Vessel positions | 15 min | No need for per-second updates |
| Marine weather | 3 hours | Models update every 1–6 hours anyway |
| BDI | 24 hours | Published once per day |
| Port coordinates | Never | Static data |

**Cache schema (SQLite):**
```sql
CREATE TABLE cache (
    key        TEXT PRIMARY KEY,
    data       TEXT,
    fetched_at INTEGER
);
```

**Resilience:** If an API is down or rate-limited, the last cached value is served with a "last updated X ago" label. The app never crashes due to an API failure.

---

## Deployment

- **Platform:** Streamlit Cloud (free tier)
- **Trigger:** Auto-redeploys on every push to `main`
- **Secrets:** `AISSTREAM_API_KEY` set in Streamlit Cloud environment settings — never in the repo
- **GitHub repo:** Public, polished README with live demo link, architecture diagram, and screenshots

---

## Build Phases

| Phase | Deliverable |
|---|---|
| 1 | Project scaffold + `db/` cache layer + `ports.json` |
| 2 | `services/aisstream.py` + Vessel Map page |
| 3 | `services/congestion.py` + Port Congestion page |
| 4 | `services/weather.py` + Delay Forecast page |
| 5 | `services/shipping_rates.py` + Supplier Risk page |
| 6 | `app.py` home dashboard |
| 7 | README + polish + Streamlit Cloud deploy |

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.11+ | Core language |
| Streamlit | UI + deployment |
| Plotly | Maps + charts |
| websockets | AISstream WebSocket client |
| httpx | REST API calls |
| yfinance | Baltic Dry Index |
| sqlite3 | Caching layer |
| python-dotenv | Environment variables |
| pandas | Data manipulation |

---

## Out of Scope (v1)

- Open-ocean vessel tracking (requires paid satellite AIS)
- User authentication or multi-user sessions
- Email/SMS alerts
- ML-based forecasting (rule-based scoring used instead)
- Mobile-optimized UI
