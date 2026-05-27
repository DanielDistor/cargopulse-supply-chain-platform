import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream
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
    try:
        from services import weather as weather_svc
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
    except ImportError:
        st.warning("Weather service not yet available.")

st.plotly_chart(fig, use_container_width=True)

# Vessel table
with st.expander("📋 All tracked vessels"):
    st.dataframe(
        df[["name", "mmsi", "speed", "heading", "lat", "lon", "timestamp"]].sort_values(
            "name"
        ),
        use_container_width=True,
    )
