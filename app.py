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
avg_delay = round(sum(p["avg_delay_days"] for p in ports) / len(ports), 1)
global_risk = "HIGH" if critical_count > 3 else "MODERATE" if high_risk_count > 5 else "LOW"

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
