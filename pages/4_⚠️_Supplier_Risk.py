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
c3.metric("BDI trend", bdi.get("trend", "N/A").upper(), delta=f"{bdi.get('change_pct_1d') or 0:.1f}% today")

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
        f"Wave height = {row['wave_height_m'] if row['wave_height_m'] is not None else 'N/A'} m (30% weight) · "
        f"BDI trend = {row['bdi_trend']} (10% weight)"
    )
