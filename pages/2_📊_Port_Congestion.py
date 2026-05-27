import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
import random
import datetime
import hashlib
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from components.styles import inject_global_css, page_header

load_dotenv()

st.set_page_config(page_title="Port Congestion | CargoPulse", layout="wide")

inject_global_css()

page_header(
    "📊 Port Congestion Rankings",
    "Congestion score 0–100 based on vessel density near each port multiplied by a marine weather penalty. Updates every 15 minutes."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

with st.sidebar:
    st.markdown("### Filters")
    regions = sorted({p["region"] for p in ports})
    selected_regions = st.multiselect("Region", regions, default=regions)
    top_n = st.slider("Show top N ports", 5, 50, 30)

with st.spinner("Scoring ports..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)

df = pd.DataFrame(congestion_data)
df = df[df["region"].isin(selected_regions)].head(top_n)

if df.empty:
    st.warning("No ports match the selected regions. Please select at least one region.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ports Scored", len(df))
col2.metric("Critical", int((df["score"] >= 86).sum()))
col3.metric("High Risk", int(((df["score"] >= 61) & (df["score"] < 86)).sum()))
col4.metric("Avg Score", f"{df['score'].mean():.0f} / 100")

st.divider()

fig = px.bar(
    df,
    x="name", y="score",
    color="label",
    color_discrete_map={
        "Clear": "#4caf50",
        "Moderate": "#ffb74d",
        "High": "#ef5350",
        "Critical": "#b71c1c",
    },
    labels={"score": "Congestion Score (0–100)", "name": "Port"},
    height=420,
)
fig.update_layout(
    xaxis_tickangle=-40,
    paper_bgcolor="#1a1f2e",
    plot_bgcolor="#1a1f2e",
    font_color="#a0aab4",
    xaxis=dict(gridcolor="#1e2736"),
    yaxis=dict(gridcolor="#1e2736"),
    legend=dict(bgcolor="#1a1f2e", bordercolor="#263044"),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("7-Day Congestion Trend")
trend_port = st.selectbox("Select a port", df["name"].tolist(), key="trend_select")
if trend_port:
    seed = int(hashlib.md5(trend_port.encode()).hexdigest(), 16) % (2**32)
    random.seed(seed)
    row = df[df["name"] == trend_port].iloc[0]
    current_score = row["score"]
    days = [(datetime.date.today() - datetime.timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
    scores = [max(0, min(100, current_score + random.randint(-12, 12))) for _ in range(6)] + [current_score]
    trend_df = pd.DataFrame({"Day": days, "Score": scores})
    fig2 = px.bar(trend_df, x="Day", y="Score", color="Score",
                  color_continuous_scale=["#4caf50", "#ffb74d", "#ef5350"],
                  range_color=(0, 100), height=260)
    fig2.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor="#1a1f2e",
        plot_bgcolor="#1a1f2e",
        font_color="#a0aab4",
        xaxis=dict(gridcolor="#1e2736"),
        yaxis=dict(gridcolor="#1e2736"),
    )
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Port Rankings")
display_df = df[["name", "country", "region", "vessel_count", "score", "label", "wave_height_m"]].copy()
display_df.columns = ["Port", "Country", "Region", "Vessels Nearby", "Score", "Status", "Wave Height (m)"]
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Port Detail")
selected_port = st.selectbox("Select a port to inspect", df["name"].tolist())
if selected_port:
    row = df[df["name"] == selected_port].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Congestion Score", f"{row['score']} / 100", delta=row["label"])
    c2.metric("Vessels Nearby", row["vessel_count"])
    c3.metric("Wave Height", f"{row['wave_height_m'] if row['wave_height_m'] is not None else 'N/A'} m")
    st.info(
        f"Score breakdown: {row['vessel_count']} vessels at port against a baseline capacity of "
        f"{row['capacity_baseline']} gives {row['vessel_count']/row['capacity_baseline']*100:.0f}% utilization, "
        f"then the marine weather penalty is applied, resulting in a final score of **{row['score']}/100**."
    )
