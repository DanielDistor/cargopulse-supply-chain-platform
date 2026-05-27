import json
import math
import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from db import cache
from components.styles import inject_global_css, page_header

load_dotenv()

st.set_page_config(page_title="Vessel Tracking | CargoPulse", layout="wide")
inject_global_css()
page_header(
    "Live Vessel Tracking",
    "Vessel positions within ~50 nautical miles of major ports via terrestrial AIS. Color = movement status."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

ANCHORED_STATUSES = {1, 5}
UNDERWAY_STATUSES = {0, 8}

COLOR_MAP = {
    "Underway":           "#4caf50",
    "Slow / Maneuvering": "#ffb74d",
    "Anchored / Moored":  "#ef5350",
}

# ── Maritime risk zones ───────────────────────────────────────────────
RISK_ZONES = [
    {"name": "Gulf of Aden",     "lat": 12.5,  "lon":  47.5, "radius_km": 450, "type": "Piracy",        "color": "#ef5350"},
    {"name": "Red Sea Corridor", "lat": 19.0,  "lon":  38.5, "radius_km": 480, "type": "Security",      "color": "#ff7043"},
    {"name": "Hormuz Strait",    "lat": 26.6,  "lon":  56.3, "radius_km": 100, "type": "Geopolitical",  "color": "#ce93d8"},
    {"name": "Malacca Strait",   "lat":  3.0,  "lon": 101.5, "radius_km": 160, "type": "Congestion",    "color": "#ffb74d"},
    {"name": "South China Sea",  "lat": 13.5,  "lon": 113.0, "radius_km": 650, "type": "Congestion",    "color": "#ffb74d"},
    {"name": "Taiwan Strait",    "lat": 24.5,  "lon": 119.5, "radius_km": 110, "type": "Geopolitical",  "color": "#ce93d8"},
    {"name": "Suez Canal",       "lat": 30.4,  "lon":  32.4, "radius_km":  90, "type": "Congestion",    "color": "#ffb74d"},
    {"name": "Panama Canal",     "lat":  9.1,  "lon": -79.7, "radius_km":  75, "type": "Congestion",    "color": "#ffb74d"},
]

ZONE_TYPE_COLOR = {
    "Piracy":       "#ef5350",
    "Security":     "#ff7043",
    "Geopolitical": "#ce93d8",
    "Congestion":   "#ffb74d",
}


def classify_vessel(row: dict) -> str:
    nav = row.get("status")
    spd = row.get("speed") or 0.0
    if nav in ANCHORED_STATUSES or (nav not in UNDERWAY_STATUSES and spd < 1.0):
        return "Anchored / Moored"
    if spd >= 5.0 or nav in UNDERWAY_STATUSES:
        return "Underway"
    return "Slow / Maneuvering"


def _hex_to_rgba(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _circle_latlons(lat: float, lon: float, radius_km: float, n: int = 60):
    lats, lons = [], []
    for i in range(n + 1):
        ang = 2 * math.pi * i / n
        dlat = (radius_km / 111.0) * math.cos(ang)
        dlon = (radius_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(ang)
        lats.append(lat + dlat)
        lons.append(lon + dlon)
    return lats, lons


# ── Inline controls ───────────────────────────────────────────────────
c1, c2, c3, _, c_btn = st.columns([1.4, 1.4, 1.4, 2.5, 1.5])
with c1:
    show_ports = st.toggle("Port congestion rings", value=True)
with c2:
    show_risk_zones = st.toggle("Maritime risk zones", value=True)
with c3:
    show_weather = st.toggle("Wave height overlay", value=False)
with c_btn:
    if st.button("Refresh Data", type="primary", use_container_width=True):
        from db.cache import _connect
        with _connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (aisstream.VESSEL_CACHE_KEY,))
        st.rerun()

with st.spinner("Fetching live vessel positions..."):
    vessels = aisstream.get_vessels(bounding_boxes)

age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)
if age is not None:
    st.caption(f"Last updated {age // 60}m {age % 60}s ago · **{len(vessels)} vessels** tracked")
else:
    st.caption("No cached data yet. Fetching now...")

if not vessels:
    st.warning("No vessel data available. Check that AISSTREAM_API_KEY is set and try refreshing.")
    st.stop()

df = pd.DataFrame(vessels).dropna(subset=["lat", "lon"])
df["category"] = df.apply(classify_vessel, axis=1)
cat_order = list(COLOR_MAP.keys())
df["category"] = pd.Categorical(df["category"], categories=cat_order, ordered=True)
df = df.sort_values("category")

total    = len(df)
underway = int((df["category"] == "Underway").sum())
slow     = int((df["category"] == "Slow / Maneuvering").sum())
anchored = int((df["category"] == "Anchored / Moored").sum())

# ── Fleet stats row — uniform fixed-height cards ──────────────────────
def fleet_card(label: str, value: int, pct: float, dot_color: str) -> str:
    dot = f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{dot_color};margin-right:6px;vertical-align:middle;flex-shrink:0"></span>'
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;'
        f'padding:16px 18px;height:96px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="display:flex;align-items:center;color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{dot}{label}</div>'
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{dot_color};font-size:12px">{pct:.0f}% of fleet</div>'
        f'</div>'
    )

s1, s2, s3, s4 = st.columns(4)
s1.markdown(
    f'<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;'
    f'padding:16px 18px;height:96px;display:flex;flex-direction:column;justify-content:space-between;">'
    f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">Total Vessels</div>'
    f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{total}</div>'
    f'<div style="color:#6b7fa3;font-size:12px">tracked right now</div>'
    f'</div>',
    unsafe_allow_html=True,
)
s2.markdown(fleet_card("Underway",           underway, underway/total*100  if total else 0, "#4caf50"), unsafe_allow_html=True)
s3.markdown(fleet_card("Slow / Maneuvering", slow,     slow/total*100      if total else 0, "#ffb74d"), unsafe_allow_html=True)
s4.markdown(fleet_card("Anchored / Moored",  anchored, anchored/total*100  if total else 0, "#ef5350"), unsafe_allow_html=True)

st.divider()

# ── Inline legend ─────────────────────────────────────────────────────
leg_html = '<div style="display:flex;gap:20px;flex-wrap:wrap;align-items:center;padding:4px 0;margin-bottom:6px;">'
leg_html += '<span style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-right:4px">Vessels</span>'
for label, color in COLOR_MAP.items():
    leg_html += (
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<div style="width:9px;height:9px;border-radius:50%;background:{color};flex-shrink:0"></div>'
        f'<span style="color:#a0aab4;font-size:12px">{label}</span>'
        f'</div>'
    )
if show_risk_zones:
    leg_html += '<span style="color:#263044;margin:0 8px">|</span>'
    leg_html += '<span style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-right:4px">Risk Zones</span>'
    for rtype, rcolor in ZONE_TYPE_COLOR.items():
        leg_html += (
            f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<div style="width:9px;height:9px;border-radius:2px;background:{rcolor};opacity:0.85;flex-shrink:0"></div>'
            f'<span style="color:#a0aab4;font-size:12px">{rtype}</span>'
            f'</div>'
        )
leg_html += '</div>'
st.markdown(leg_html, unsafe_allow_html=True)

# ── Full-width map ────────────────────────────────────────────────────
fig = px.scatter_mapbox(
    df, lat="lat", lon="lon",
    color="category",
    color_discrete_map=COLOR_MAP,
    category_orders={"category": cat_order},
    hover_name="name",
    hover_data={
        "mmsi": True, "speed": True, "heading": True,
        "category": True, "lat": False, "lon": False,
    },
    zoom=1, height=580,
    mapbox_style="carto-darkmatter",
)
fig.update_traces(marker=dict(size=6, opacity=0.9))
fig.update_layout(
    margin={"r": 0, "t": 0, "l": 0, "b": 0},
    paper_bgcolor="#1a1f2e",
    showlegend=False,
)

# Risk zones go behind vessels (prepend traces)
if show_risk_zones:
    risk_traces = []
    for zone in RISK_ZONES:
        clat, clon = _circle_latlons(zone["lat"], zone["lon"], zone["radius_km"])
        risk_traces.append(go.Scattermapbox(
            lat=clat, lon=clon,
            mode="lines",
            fill="toself",
            fillcolor=_hex_to_rgba(zone["color"], 0.10),
            line=dict(color=zone["color"], width=1.2),
            showlegend=False,
            hovertemplate=f"<b>{zone['name']}</b><br>Type: {zone['type']}<br>Radius: ~{zone['radius_km']} km<extra></extra>",
        ))
        risk_traces.append(go.Scattermapbox(
            lat=[zone["lat"]], lon=[zone["lon"]],
            mode="text",
            text=[zone["name"]],
            textposition="middle center",
            textfont=dict(color=zone["color"], size=9),
            showlegend=False,
            hoverinfo="skip",
        ))
    fig.data = tuple(risk_traces) + tuple(fig.data)

if show_ports:
    with st.spinner("Loading port congestion rings..."):
        congestion_data = cong_svc.get_all_port_congestion(vessels)
    cong_map       = {c["name"]: c for c in congestion_data}
    port_color_map = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}
    for port in ports:
        cong  = cong_map.get(port["name"], {})
        score = cong.get("score", 0)
        label = cong.get("label", "Clear")
        fig.add_trace(go.Scattermapbox(
            lat=[port["lat"]], lon=[port["lon"]],
            mode="markers",
            marker=dict(size=max(10, score / 4 + 8), color=port_color_map.get(label, "#9e9e9e"), opacity=0.4),
            showlegend=False,
            hovertemplate=(
                f"<b>{port['name']}</b> (port)<br>"
                f"Congestion: {score}/100 — {label}<br>"
                f"Vessels nearby: {cong.get('vessel_count', 0)}<extra></extra>"
            ),
        ))

if show_weather and ports:
    try:
        from services import weather as weather_svc
        wx_lats, wx_lons, wx_heights = [], [], []
        for p in ports[::5]:
            w = weather_svc.get_marine_weather(p["lat"], p["lon"])
            if w.get("wave_height_m") is not None:
                wx_lats.append(p["lat"]); wx_lons.append(p["lon"]); wx_heights.append(w["wave_height_m"])
        if wx_lats:
            fig.add_trace(go.Scattermapbox(
                lat=wx_lats, lon=wx_lons, mode="markers",
                marker=dict(size=14, color=wx_heights, colorscale="Blues",
                            showscale=True, colorbar=dict(title="Wave (m)"), opacity=0.5),
                name="Wave height", showlegend=False,
                hovertemplate="Wave: %{marker.color:.1f} m<extra></extra>",
            ))
    except ImportError:
        st.warning("Weather service is not available.")

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Vessel table ──────────────────────────────────────────────────────
st.markdown('<div style="color:#e8eaed;font-size:15px;font-weight:700;margin-bottom:8px;">All Vessels</div>', unsafe_allow_html=True)
display_df = df[["name", "category", "speed", "heading"]].copy()
display_df.columns = ["Vessel", "Status", "Speed (kn)", "Heading"]
st.dataframe(display_df.sort_values("Speed (kn)", ascending=False),
             use_container_width=True, height=320, hide_index=True)
