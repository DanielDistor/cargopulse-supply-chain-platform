import json
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

st.set_page_config(page_title="Vessel Map | CargoPulse", layout="wide")
inject_global_css()
page_header(
    "🗺️ Live Vessel Map",
    "Vessel positions within ~50 nautical miles of major ports via terrestrial AIS. Port congestion rings show live scoring."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

with st.sidebar:
    st.markdown("### Controls")
    show_ports = st.toggle("Show port congestion rings", value=True)
    show_weather = st.toggle("Show wave height overlay", value=False)
    duration = st.slider("AIS fetch duration (seconds)", min_value=5, max_value=30, value=10)
    if st.button("🔄 Refresh Data"):
        from db.cache import _connect
        with _connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (aisstream.VESSEL_CACHE_KEY,))
        st.rerun()

with st.spinner("Fetching live vessel positions..."):
    vessels = aisstream.get_vessels(bounding_boxes, duration_seconds=duration)

age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)
if age is not None:
    st.caption(f"🟢 Last updated {age // 60}m {age % 60}s ago · **{len(vessels)} vessels** tracked")
else:
    st.caption("⚠️ No cached data yet. Fetching now...")

if not vessels:
    st.warning("No vessel data available. Check that AISSTREAM_API_KEY is set and try refreshing.")
    st.stop()

df = pd.DataFrame(vessels).dropna(subset=["lat", "lon"])

map_col, stats_col = st.columns([3, 1])

with map_col:
    fig = px.scatter_mapbox(
        df, lat="lat", lon="lon",
        hover_name="name",
        hover_data={"mmsi": True, "speed": True, "heading": True, "lat": False, "lon": False},
        color_discrete_sequence=["#00d4ff"],
        zoom=1, height=600,
        mapbox_style="carto-darkmatter",
    )
    fig.update_traces(marker=dict(size=6, opacity=0.85))
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="#1a1f2e")

    if show_ports:
        # Score all ports and overlay congestion rings
        with st.spinner("Loading port congestion data..."):
            congestion_data = cong_svc.get_all_port_congestion(vessels)
        cong_map = {c["name"]: c for c in congestion_data}
        color_map = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}
        for port in ports:
            cong = cong_map.get(port["name"], {})
            score = cong.get("score", 0)
            label = cong.get("label", "Clear")
            fig.add_trace(go.Scattermapbox(
                lat=[port["lat"]], lon=[port["lon"]],
                mode="markers",
                marker=dict(
                    size=max(10, score / 4 + 8),
                    color=color_map.get(label, "#9e9e9e"),
                    opacity=0.45,
                ),
                showlegend=False,
                hovertemplate=(
                    f"<b>{port['name']}</b> (port)<br>"
                    f"Congestion: {score}/100 — {label}<br>"
                    f"Vessels nearby: {cong.get('vessel_count', 0)}"
                    "<extra></extra>"
                ),
            ))

    if show_weather and ports:
        try:
            from services import weather as weather_svc
            sampled = ports[::5]
            wx_lats, wx_lons, wx_heights = [], [], []
            for p in sampled:
                w = weather_svc.get_marine_weather(p["lat"], p["lon"])
                if w.get("wave_height_m") is not None:
                    wx_lats.append(p["lat"])
                    wx_lons.append(p["lon"])
                    wx_heights.append(w["wave_height_m"])
            if wx_lats:
                fig.add_trace(go.Scattermapbox(
                    lat=wx_lats, lon=wx_lons,
                    mode="markers",
                    marker=dict(size=14, color=wx_heights, colorscale="Blues",
                                showscale=True, colorbar=dict(title="Wave (m)"), opacity=0.5),
                    name="Wave height",
                    hovertemplate="Wave: %{marker.color:.1f} m<extra></extra>",
                ))
        except ImportError:
            st.warning("Weather service is not available.")

    st.plotly_chart(fig, use_container_width=True)

with stats_col:
    st.markdown("#### Fleet Stats")

    # Speed distribution
    speeds = df["speed"].dropna()
    anchored = int((speeds < 1.0).sum())
    slow = int(((speeds >= 1.0) & (speeds < 5.0)).sum())
    underway = int((speeds >= 5.0).sum())
    total = len(speeds)

    for label, count, color in [("Anchored / Drifting", anchored, "#ef5350"),
                                  ("Slow / Maneuvering", slow, "#ffb74d"),
                                  ("Underway", underway, "#4caf50")]:
        pct = count / total * 100 if total else 0
        st.markdown(
            f'<div style="padding:10px 14px;margin:6px 0;background:#1a1f2e;border-left:3px solid {color};border-radius:0 8px 8px 0;">'
            f'<div style="color:#a0aab4;font-size:11px;text-transform:uppercase;letter-spacing:.06em">{label}</div>'
            f'<div style="display:flex;align-items:baseline;gap:8px;">'
            f'<span style="color:#e8eaed;font-size:22px;font-weight:800">{count}</span>'
            f'<span style="color:#5a6a7e;font-size:13px">{pct:.0f}%</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Speed histogram
    if len(speeds) > 0:
        fig_speed = px.histogram(speeds, nbins=20, height=200,
                                  labels={"value": "Speed (knots)", "count": "Vessels"})
        fig_speed.update_traces(marker_color="#00d4ff", opacity=0.8)
        fig_speed.update_layout(
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
            xaxis=dict(gridcolor="#1e2736", title="Speed (kn)"),
            yaxis=dict(gridcolor="#1e2736", title=""),
            title="Speed Distribution",
            title_font_color="#e8eaed",
            showlegend=False,
        )
        st.plotly_chart(fig_speed, use_container_width=True)

    st.markdown("#### All Vessels")
    st.dataframe(
        df[["name", "speed", "heading"]].sort_values("speed", ascending=False),
        use_container_width=True, height=200,
    )
