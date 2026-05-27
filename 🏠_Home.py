import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from db import cache
from components.styles import inject_global_css, page_header

load_dotenv()

st.set_page_config(
    page_title="CargoPulse | Supply Chain Intelligence",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()

page_header(
    "🚢 CargoPulse",
    "Real-time supply chain risk intelligence — vessel tracking, congestion, delay forecasting, and supplier risk monitoring."
)

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

st.caption(f"🟢 Live data · refreshed {age_str} · {len(vessels)} vessels tracked across {len(ports)} ports")
st.divider()

k1, k2, k3, k4 = st.columns(4)
critical_count = int((df_cong["score"] >= 86).sum())
high_risk_count = int(((df_cong["score"] >= 61) & (df_cong["score"] < 86)).sum())
avg_delay = round(sum(p["avg_delay_days"] for p in ports) / len(ports), 1)
global_risk = "HIGH" if critical_count > 3 else "MODERATE" if high_risk_count > 5 else "LOW"

k1.metric("Vessels Tracked", f"{len(vessels):,}")
k2.metric("Global Risk Level", global_risk, delta=f"{critical_count} critical ports")
k3.metric("Congested Ports", critical_count + high_risk_count)
k4.metric("Avg Baseline Delay", f"+{avg_delay} days")

st.divider()

col_map, col_table = st.columns([2, 1])

with col_map:
    st.subheader("Live Vessel Positions")
    if vessels:
        df_v = pd.DataFrame(vessels).dropna(subset=["lat", "lon"])
        fig = px.scatter_mapbox(
            df_v, lat="lat", lon="lon",
            hover_name="name",
            zoom=1, height=400,
            mapbox_style="carto-darkmatter",
            color_discrete_sequence=["#00d4ff"],
        )
        fig.update_traces(marker=dict(size=5, opacity=0.85))
        fig.update_layout(
            margin=dict(r=0, t=0, l=0, b=0),
            paper_bgcolor="#1a1f2e",
            plot_bgcolor="#1a1f2e",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No vessel data available yet. The map will populate once AISstream data loads.")

with col_table:
    st.subheader("Top Congested Ports")
    top5 = df_cong.head(5)[["name", "score", "label"]]
    for _, row in top5.iterrows():
        icon = {"Clear": "🟢", "Moderate": "🟡", "High": "🔴", "Critical": "⚫"}.get(row["label"], "⚪")
        st.markdown(
            f'<div style="padding:10px 14px;margin:6px 0;background:#1a1f2e;'
            f'border-left:3px solid {"#4caf50" if row["label"]=="Clear" else "#ffb74d" if row["label"]=="Moderate" else "#ef5350" if row["label"]=="High" else "#212121"};'
            f'border-radius:0 8px 8px 0;">'
            f'{icon} <strong style="color:#e8eaed">{row["name"]}</strong>'
            f'<span style="float:right;color:#6b7fa3;font-size:13px">{row["score"]}/100</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()
st.caption("Use the sidebar to navigate between Vessel Map, Port Congestion, Delay Forecast, and Supplier Risk.")
