# CargoPulse — Data Sources & Known Limitations

## Data Sources

| Layer | Source | Type | Refresh Rate | Key Required |
|---|---|---|---|---|
| Live vessel positions | [AISstream.io](https://aisstream.io) | WebSocket (real-time) | Seconds | Yes (`.env`) |
| Marine weather | [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api) | REST (free, no key) | Every 1–6 hours | No |
| Port congestion score | Computed from AISstream vessel density | Derived metric | Same as AISstream | No |
| Shipping rates (BDI) | [Yahoo Finance via yfinance](https://pypi.org/project/yfinance/) `^BDIY` | REST (free, no key) | Daily | No |
| Port coordinates | Static JSON (`db/ports.json`) | Static file | Never (ports don't move) | No |

---

## Known Limitations

### 🚢 Vessel Tracking Coverage

**What we capture:**
- All vessels within approximately **40–50 nautical miles (~75–92 km) of coastlines** via terrestrial AIS receivers
- This includes vessels docked at ports, anchored offshore, and on final approach
- Coverage is strongest near busy ports with dense AIS receiver networks (Shanghai, LA, Rotterdam, Singapore, etc.)

**What we cannot capture:**
- Vessels currently sailing in **open ocean**, more than ~50 nautical miles from the nearest coastline
- This means a container ship that departed Shanghai 3 days ago and is mid-Pacific en route to Los Angeles will **not appear** on the map until it reaches the US West Coast approach zone
- Satellites are required for full open-ocean AIS coverage — this requires a paid API (e.g., MarineTraffic, Spire Maritime, ORBCOMM)

**Impact on dashboard features:**
- Port congestion scoring is **not affected** — we measure vessels at/near the port, which terrestrial AIS covers fully
- Delay forecasting uses congestion + weather + historical patterns, **not** individual open-ocean ship tracking
- The vessel map accurately reflects the maritime picture within port approach zones

**Future upgrade path:**
Satellite AIS coverage can be added by integrating a paid provider (e.g., MarineTraffic API or Spire Maritime). The `services/aisstream.py` module is designed to be swapped out without changes to the rest of the app.

---

### 🌊 Marine Weather

- Open-Meteo updates every 1–6 hours depending on the model (not real-time)
- Accuracy in coastal areas is limited for tides and ocean currents; not suitable for navigation
- Wave and weather data is used for **risk scoring only**, not precise navigational guidance

---

### 📊 Baltic Dry Index (BDI)

- The BDI is published **once per day** by the Baltic Exchange in London
- This is the same frequency as any paid API — daily is the maximum resolution available anywhere
- yfinance retrieves the same data as expensive financial data subscriptions for this specific index

---

### ⚙️ Rate Limits & Caching

- AISstream.io free tier: WebSocket connection with generous limits; see [aisstream.io/pricing](https://aisstream.io) for current terms
- Open-Meteo: 10,000 API calls/day free for non-commercial use
- All API responses are cached in SQLite (`db/cache.db`) with per-source TTLs to stay within free limits:
  - Vessel positions: 15-minute cache
  - Weather: 3-hour cache
  - BDI: 24-hour cache

---

*Last updated: 2026-05-27*
