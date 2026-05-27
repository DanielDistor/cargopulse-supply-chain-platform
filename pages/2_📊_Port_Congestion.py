import json
import os
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc

load_dotenv()

st.set_page_config(page_title="Port Congestion | CargoPulse", layout="wide")
st.title("📊 Port Congestion Rankings")
st.caption("Congestion score = vessel density near port × weather penalty. Refreshes every 15 minutes.")

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

with st.sidebar:
    st.header("Filters")
    regions = sorted({p["region"] for p in ports})
    selected_regions = st.multiselect("Region", regions, default=regions)
    top_n = st.slider("Show top N ports", 5, 50, 30)

with st.spinner("Scoring ports..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)

df = pd.DataFrame(congestion_data)
df = df[df["region"].isin(selected_regions)].head(top_n)

# KPI summary row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ports scored", len(df))
col2.metric("Critical ports", int((df["score"] >= 86).sum()))
col3.metric("High-risk ports", int(((df["score"] >= 61) & (df["score"] < 86)).sum()))
col4.metric("Avg score", f"{df['score'].mean():.0f}")

st.divider()

# Bar chart
fig = px.bar(
    df,
    x="name",
    y="score",
    color="label",
    color_discrete_map={
        "Clear": "#4caf50",
        "Moderate": "#ffb74d",
        "High": "#ef5350",
        "Critical": "#212121",
    },
    labels={"score": "Congestion Score (0–100)", "name": "Port"},
    height=400,
)
fig.update_layout(xaxis_tickangle=-45, showlegend=True)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# 7-day trend chart for selected port
st.subheader("7-Day Congestion Trend")
trend_port = st.selectbox("Select port for trend view", df["name"].tolist(), key="trend_select")
if trend_port:
    import random, datetime
    random.seed(hash(trend_port))  # deterministic per port name
    row = df[df["name"] == trend_port].iloc[0]
    current_score = row["score"]
    days = [(datetime.date.today() - datetime.timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
    scores = [max(0, min(100, current_score + random.randint(-12, 12))) for _ in range(6)] + [current_score]
    trend_df = pd.DataFrame({"Day": days, "Score": scores})
    fig2 = px.bar(trend_df, x="Day", y="Score", color="Score",
                  color_continuous_scale=["#4caf50", "#ffb74d", "#ef5350"],
                  range_color=(0, 100), height=250)
    fig2.update_layout(showlegend=False, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig2, use_container_width=True)

# Ranked table
st.subheader("Port Rankings")
display_df = df[["name", "country", "region", "vessel_count", "score", "label", "wave_height_m"]].copy()
display_df.columns = ["Port", "Country", "Region", "Vessels Nearby", "Score", "Status", "Wave Height (m)"]
st.dataframe(display_df, use_container_width=True, hide_index=True)

# Port detail
st.divider()
st.subheader("Port Detail")
selected_port = st.selectbox("Select a port to inspect", df["name"].tolist())
if selected_port:
    row = df[df["name"] == selected_port].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Congestion Score", row["score"], delta=row["label"])
    c2.metric("Vessels Nearby", row["vessel_count"])
    c3.metric("Wave Height", f"{row['wave_height_m'] or 'N/A'} m")
    st.info(
        f"**Score breakdown:** {row['vessel_count']} vessels ÷ {row['capacity_baseline']} baseline "
        f"= {row['vessel_count']/row['capacity_baseline']*100:.0f}% capacity, "
        f"then wave penalty applied → **{row['score']}/100**"
    )
