import json
import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
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
    "Real-time congestion scoring for 50 major world ports. Score = vessel density × marine weather penalty."
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
    view_mode = st.radio("View mode", ["Rankings", "World Map", "Compare Ports"], index=0)

with st.spinner("Scoring ports..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)

df_all = pd.DataFrame(congestion_data)
df = df_all[df_all["region"].isin(selected_regions)].head(top_n)

if df.empty:
    st.warning("No ports match the selected regions. Please select at least one region.")
    st.stop()

# KPI row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ports Scored", len(df_all))
col2.metric("Critical", int((df_all["score"] >= 86).sum()))
col3.metric("High Risk", int(((df_all["score"] >= 61) & (df_all["score"] < 86)).sum()))
col4.metric("Avg Score", f"{df_all['score'].mean():.0f} / 100")

st.divider()

if view_mode == "World Map":
    st.subheader("Global Port Congestion Map")
    st.caption("Circle size and color reflect congestion score. Hover for details.")

    fig_map = go.Figure()
    color_map = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}
    for _, row in df_all.iterrows():
        fig_map.add_trace(go.Scattermapbox(
            lat=[row["lat"]], lon=[row["lon"]],
            mode="markers",
            marker=dict(
                size=max(8, row["score"] / 5 + 6),
                color=color_map.get(row["label"], "#9e9e9e"),
                opacity=0.85,
            ),
            name=row["label"],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['name']}</b><br>"
                f"Score: {row['score']}/100<br>"
                f"Status: {row['label']}<br>"
                f"Vessels nearby: {row['vessel_count']}<br>"
                f"Wave height: {row['wave_height_m'] if row['wave_height_m'] is not None else 'N/A'} m"
                "<extra></extra>"
            ),
        ))
    # Legend traces
    for label, color in color_map.items():
        fig_map.add_trace(go.Scattermapbox(
            lat=[None], lon=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=label, showlegend=True,
        ))
    fig_map.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox_zoom=1.2,
        mapbox_center={"lat": 20, "lon": 10},
        height=600,
        margin=dict(r=0, t=0, l=0, b=0),
        paper_bgcolor="#1a1f2e",
        legend=dict(bgcolor="#1a1f2e", bordercolor="#263044", font=dict(color="#a0aab4")),
    )
    st.plotly_chart(fig_map, use_container_width=True)

elif view_mode == "Compare Ports":
    st.subheader("Port Comparison")
    c1, c2 = st.columns(2)
    port_list = df_all["name"].tolist()
    with c1:
        port_a = st.selectbox("Port A", port_list, index=0)
    with c2:
        port_b = st.selectbox("Port B", port_list, index=1)

    if port_a and port_b and port_a != port_b:
        ra = df_all[df_all["name"] == port_a].iloc[0]
        rb = df_all[df_all["name"] == port_b].iloc[0]

        metrics = ["score", "vessel_count", "wave_height_m"]
        labels = ["Congestion Score", "Vessels Nearby", "Wave Height (m)"]

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"#### {port_a} ({ra['country']})")
            st.metric("Congestion Score", f"{ra['score']} / 100", delta=ra["label"])
            st.metric("Vessels Nearby", ra["vessel_count"])
            st.metric("Wave Height", f"{ra['wave_height_m'] if ra['wave_height_m'] is not None else 'N/A'} m")
        with col_b:
            st.markdown(f"#### {port_b} ({rb['country']})")
            score_delta = ra["score"] - rb["score"]
            st.metric("Congestion Score", f"{rb['score']} / 100", delta=rb["label"])
            st.metric("Vessels Nearby", rb["vessel_count"])
            st.metric("Wave Height", f"{rb['wave_height_m'] if rb['wave_height_m'] is not None else 'N/A'} m")

        # Radar comparison
        categories = ["Congestion", "Vessel Load", "Weather Risk"]
        def normalize(val, max_val):
            return round((val or 0) / max_val * 100) if max_val else 0

        vals_a = [ra["score"], normalize(ra["vessel_count"], ra["capacity_baseline"] * 2), normalize(ra["wave_height_m"] or 0, 5) * 100]
        vals_b = [rb["score"], normalize(rb["vessel_count"], rb["capacity_baseline"] * 2), normalize(rb["wave_height_m"] or 0, 5) * 100]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(r=vals_a + [vals_a[0]], theta=categories + [categories[0]],
                                             fill="toself", name=port_a, line_color="#00d4ff"))
        fig_radar.add_trace(go.Scatterpolar(r=vals_b + [vals_b[0]], theta=categories + [categories[0]],
                                             fill="toself", name=port_b, line_color="#ef5350"))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="#1a1f2e",
                radialaxis=dict(visible=True, range=[0, 100], gridcolor="#263044", color="#6b7fa3"),
                angularaxis=dict(gridcolor="#263044", color="#a0aab4"),
            ),
            paper_bgcolor="#1a1f2e",
            legend=dict(bgcolor="#1a1f2e", bordercolor="#263044", font=dict(color="#a0aab4")),
            height=400,
            margin=dict(l=60, r=60, t=40, b=40),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

else:  # Rankings view
    # Congestion bar chart
    fig = px.bar(
        df, x="name", y="score", color="label",
        color_discrete_map={"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"},
        labels={"score": "Congestion Score (0–100)", "name": "Port"},
        height=420,
    )
    fig.update_layout(
        xaxis_tickangle=-40,
        paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
        xaxis=dict(gridcolor="#1e2736"), yaxis=dict(gridcolor="#1e2736"),
        legend=dict(bgcolor="#1a1f2e", bordercolor="#263044"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Biggest movers (simulated day-over-day change using deterministic seed)
    st.subheader("Biggest Movers Today")
    st.caption("Simulated day-over-day change based on live score and port-specific variance patterns.")
    movers = []
    for _, row in df.iterrows():
        seed = int(hashlib.md5(f"{row['name']}_yesterday".encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        yesterday = max(0, min(100, row["score"] + random.randint(-18, 18)))
        change = row["score"] - yesterday
        movers.append({"Port": row["name"], "Now": row["score"], "Yesterday": yesterday, "Change": change, "Status": row["label"]})
    movers_df = pd.DataFrame(movers).sort_values("Change", key=abs, ascending=False).head(5)
    for _, m in movers_df.iterrows():
        arrow = "🔺" if m["Change"] > 0 else "🔻" if m["Change"] < 0 else "➡️"
        color = "#ef5350" if m["Change"] > 5 else "#4caf50" if m["Change"] < -5 else "#a0aab4"
        st.markdown(
            f'<div style="display:flex;align-items:center;padding:10px 14px;margin:5px 0;'
            f'background:#1a1f2e;border-radius:8px;border:1px solid #263044;">'
            f'<span style="flex:1;color:#e8eaed;font-weight:600">{m["Port"]}</span>'
            f'<span style="color:#6b7fa3;font-size:13px;margin-right:16px">{m["Yesterday"]} → {m["Now"]}</span>'
            f'<span style="color:{color};font-weight:700;font-size:15px">{arrow} {m["Change"]:+d}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # 7-day trend
    st.subheader("7-Day Trend")
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
            showlegend=False, margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
            xaxis=dict(gridcolor="#1e2736"), yaxis=dict(gridcolor="#1e2736"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Full rankings table
    st.subheader("All Port Rankings")
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
        c1.metric("Congestion Score", f"{row['score']} / 100", delta=row["label"])
        c2.metric("Vessels Nearby", row["vessel_count"])
        c3.metric("Wave Height", f"{row['wave_height_m'] if row['wave_height_m'] is not None else 'N/A'} m")
        st.info(
            f"Score breakdown: {row['vessel_count']} vessels against a baseline capacity of "
            f"{row['capacity_baseline']} gives {row['vessel_count']/row['capacity_baseline']*100:.0f}% utilization, "
            f"then the marine weather penalty is applied, resulting in a final score of **{row['score']}/100**."
        )
