# 🚢 CargoPulse

**Real-time supply chain risk intelligence platform** — live vessel tracking, port congestion analytics, shipment delay forecasting, and supplier region risk monitoring.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

---

## Features

| Page | Description |
|---|---|
| 🏠 Home | Global KPIs, live mini-map, top congested ports at a glance |
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
git clone https://github.com/DanielDistor/cargopulse-supply-chain-platform
cd cargopulse-supply-chain-platform
pip install -r requirements.txt
cp .env.example .env          # then add your AISSTREAM_API_KEY
streamlit run Home.py
```

## Running Tests

```bash
pytest tests/ -v
```

## Tech Stack

Python · Streamlit · Plotly · websockets · httpx · yfinance · SQLite · pandas
