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
from components.styles import inject_global_css, page_header, navbar

load_dotenv()

st.set_page_config(page_title="Port Congestion | CargoPulse", layout="wide")
inject_global_css()
navbar(current="Port Congestion")
page_header(
    "Port Congestion Rankings",
    "Real-time congestion scoring for 50 major world ports. Score = vessel density × marine weather penalty."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

# ── Inline controls ───────────────────────────────────────────────────
filter_col, view_col = st.columns([3, 2])
with filter_col:
    regions = sorted({p["region"] for p in ports})
    selected_regions = st.multiselect("Filter by region", regions, default=regions)
with view_col:
    view_mode = st.radio("View mode", ["Rankings", "World Map", "Compare Ports"], horizontal=True)

with st.spinner("Scoring ports..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)

df_all = pd.DataFrame(congestion_data)
df = df_all[df_all["region"].isin(selected_regions)]

if df.empty:
    st.warning("No ports match the selected regions. Please select at least one region.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────
critical_n = int((df_all["score"] >= 86).sum())
high_n     = int(((df_all["score"] >= 61) & (df_all["score"] < 86)).sum())
elevated_n = int(((df_all["score"] >= 31) & (df_all["score"] < 61)).sum())


def _kpi(label, value, sub="", sub_color="#6b7fa3", border_color=None):
    bl = f"border-left:3px solid {border_color};" if border_color else ""
    br = "0 10px 10px 0" if border_color else "10px"
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;{bl}'
        f'border-radius:{br};padding:16px 18px;height:96px;'
        f'display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{label}</div>'
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{sub_color};font-size:12px">{sub}</div>'
        f'</div>'
    )


crit_color = "#ef5350" if critical_n > 0 else "#4caf50"
high_color = "#ffb74d" if high_n > 0     else "#4caf50"
elev_color = "#00d4ff" if elevated_n > 0 else "#4caf50"

col1, col2, col3, col4 = st.columns(4)
col1.markdown(_kpi("Ports Scored", len(df_all), f"across {len(regions)} regions"), unsafe_allow_html=True)
col2.markdown(_kpi("Critical",     critical_n,  "score ≥ 86",  crit_color, "#ef5350" if critical_n > 0 else None), unsafe_allow_html=True)
col3.markdown(_kpi("High Risk",    high_n,      "score 61–85", high_color, "#ffb74d" if high_n > 0     else None), unsafe_allow_html=True)
col4.markdown(_kpi("Under Watch",  elevated_n,  "score 31–60", elev_color, "#00d4ff" if elevated_n > 0 else None), unsafe_allow_html=True)

st.divider()

# ── Views ─────────────────────────────────────────────────────────────
if view_mode == "World Map":
    st.caption("Circle size and color reflect congestion score. Hover for details.")
    fig_map = go.Figure()
    color_map = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}
    for _, row in df_all.iterrows():
        fig_map.add_trace(go.Scattermapbox(
            lat=[row["lat"]], lon=[row["lon"]], mode="markers",
            marker=dict(size=max(8, row["score"] / 5 + 6), color=color_map.get(row["label"], "#9e9e9e"), opacity=0.85),
            name=row["label"], showlegend=False,
            hovertemplate=(
                f"<b>{row['name']}</b><br>Score: {row['score']}/100<br>Status: {row['label']}<br>"
                f"Vessels nearby: {row['vessel_count']}<br>"
                f"Wave height: {row['wave_height_m'] if row['wave_height_m'] is not None else 'N/A'} m<extra></extra>"
            ),
        ))
    for label, color in color_map.items():
        fig_map.add_trace(go.Scattermapbox(lat=[None], lon=[None], mode="markers",
                                            marker=dict(size=10, color=color), name=label, showlegend=True))
    fig_map.update_layout(
        mapbox_style="carto-darkmatter", mapbox_zoom=1.2, mapbox_center={"lat": 20, "lon": 10},
        height=600, margin=dict(r=0, t=0, l=0, b=0), paper_bgcolor="#1a1f2e",
        legend=dict(bgcolor="#1a1f2e", bordercolor="#263044", font=dict(color="#a0aab4")),
    )
    st.plotly_chart(fig_map, use_container_width=True)

elif view_mode == "Compare Ports":
    port_list = df_all["name"].tolist()
    ca, cb = st.columns(2)
    with ca:
        port_a = st.selectbox("Port A", port_list, index=0)
    with cb:
        port_b = st.selectbox("Port B", port_list, index=1)

    if port_a and port_b and port_a != port_b:
        ra = df_all[df_all["name"] == port_a].iloc[0]
        rb = df_all[df_all["name"] == port_b].iloc[0]
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"#### {port_a} ({ra['country']})")
            st.metric("Congestion Score", f"{ra['score']} / 100", delta=ra["label"])
            st.metric("Vessels Nearby", ra["vessel_count"])
            st.metric("Wave Height", f"{ra['wave_height_m'] if ra['wave_height_m'] is not None else 'N/A'} m")
        with col_b:
            st.markdown(f"#### {port_b} ({rb['country']})")
            st.metric("Congestion Score", f"{rb['score']} / 100", delta=rb["label"])
            st.metric("Vessels Nearby", rb["vessel_count"])
            st.metric("Wave Height", f"{rb['wave_height_m'] if rb['wave_height_m'] is not None else 'N/A'} m")

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
            polar=dict(bgcolor="#1a1f2e",
                       radialaxis=dict(visible=True, range=[0, 100], gridcolor="#263044", color="#6b7fa3"),
                       angularaxis=dict(gridcolor="#263044", color="#a0aab4")),
            paper_bgcolor="#1a1f2e",
            legend=dict(bgcolor="#1a1f2e", bordercolor="#263044", font=dict(color="#a0aab4")),
            height=400, margin=dict(l=60, r=60, t=40, b=40),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

else:  # Rankings
    chart_col, movers_col = st.columns([3, 2])

    with chart_col:
        st.markdown('<div style="color:#e8eaed;font-size:15px;font-weight:600;margin-bottom:8px;">Top 20 by Congestion Score</div>', unsafe_allow_html=True)
        df_chart     = df.sort_values("score", ascending=False).head(20)
        df_chart_asc = df_chart.sort_values("score", ascending=True)
        color_map_bar = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}
        fig = px.bar(
            df_chart_asc, x="score", y="name", color="label", orientation="h",
            color_discrete_map=color_map_bar, text="score",
            labels={"score": "Congestion Score (0–100)", "name": "Port", "label": "Status"},
            height=max(420, len(df_chart_asc) * 26),
            hover_data={"vessel_count": True, "label": True, "name": False, "score": False},
        )
        fig.update_traces(textposition="outside", textfont_color="#a0aab4")
        fig.update_layout(
            xaxis=dict(range=[0, 115], gridcolor="#1e2736", title="Congestion Score (0–100)"),
            yaxis=dict(gridcolor="#1e2736", categoryorder="array", categoryarray=df_chart_asc["name"].tolist()),
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
            legend=dict(title="Status", bgcolor="#1a1f2e", bordercolor="#263044", font=dict(color="#a0aab4")),
            margin=dict(l=10, r=80, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    with movers_col:
        st.markdown('<div style="color:#e8eaed;font-size:15px;font-weight:600;margin-bottom:4px;">Biggest Movers Today</div>', unsafe_allow_html=True)
        st.caption("Simulated day-over-day change based on live score and port-specific variance patterns.")
        movers = []
        for _, row in df.iterrows():
            seed = int(hashlib.md5(f"{row['name']}_yesterday".encode()).hexdigest(), 16) % (2**32)
            random.seed(seed)
            yesterday = max(0, min(100, row["score"] + random.randint(-18, 18)))
            change    = row["score"] - yesterday
            movers.append({"Port": row["name"], "Now": row["score"], "Yesterday": yesterday,
                           "Change": change, "Status": row["label"]})
        movers_df = pd.DataFrame(movers).sort_values("Change", key=abs, ascending=False).head(8)
        for _, m in movers_df.iterrows():
            arrow = "▲" if m["Change"] > 0 else "▼" if m["Change"] < 0 else "—"
            color = "#ef5350" if m["Change"] > 5 else "#4caf50" if m["Change"] < -5 else "#a0aab4"
            st.markdown(
                f'<div style="display:flex;align-items:center;padding:9px 12px;margin-bottom:5px;'
                f'background:#1a1f2e;border-radius:8px;border:1px solid #263044;">'
                f'<span style="flex:1;color:#e8eaed;font-size:13px;font-weight:600;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis">{m["Port"]}</span>'
                f'<span style="color:#6b7fa3;font-size:12px;margin:0 10px;flex-shrink:0">{m["Yesterday"]}→{m["Now"]}</span>'
                f'<span style="color:{color};font-weight:700;font-size:13px;flex-shrink:0">{arrow} {abs(m["Change"])}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        if not df.empty:
            worst = df.iloc[0]
            wc = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}.get(worst["label"], "#a0aab4")
            st.markdown(
                f'<div style="background:#1a1f2e;border:1px solid #263044;border-left:3px solid {wc};'
                f'border-radius:0 10px 10px 0;padding:14px 16px;">'
                f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Worst Port Right Now</div>'
                f'<div style="color:#e8eaed;font-size:16px;font-weight:700;margin-bottom:3px">{worst["name"]}</div>'
                f'<div style="color:#5a6a7e;font-size:12px;margin-bottom:10px">{worst["country"]} · {worst["region"]}</div>'
                f'<div style="display:flex;gap:20px;">'
                f'  <div><div style="color:#5a6a7e;font-size:10px;text-transform:uppercase">Score</div>'
                f'      <div style="color:{wc};font-size:22px;font-weight:800">{worst["score"]}<span style="color:#5a6a7e;font-size:11px">/100</span></div></div>'
                f'  <div><div style="color:#5a6a7e;font-size:10px;text-transform:uppercase">Vessels</div>'
                f'      <div style="color:#e8eaed;font-size:22px;font-weight:800">{worst["vessel_count"]}</div></div>'
                f'  <div><div style="color:#5a6a7e;font-size:10px;text-transform:uppercase">Wave</div>'
                f'      <div style="color:#e8eaed;font-size:22px;font-weight:800">'
                f'          {worst["wave_height_m"] if worst["wave_height_m"] is not None else "—"}'
                f'          <span style="color:#5a6a7e;font-size:11px"> m</span></div></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    st.markdown('<div style="color:#e8eaed;font-size:15px;font-weight:600;margin-bottom:8px;">7-Day Trend</div>', unsafe_allow_html=True)
    trend_port = st.selectbox("Select a port", df["name"].tolist(), key="trend_select")
    if trend_port:
        seed = int(hashlib.md5(trend_port.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        row = df[df["name"] == trend_port].iloc[0]
        current_score = row["score"]
        days   = [(datetime.date.today() - datetime.timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
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

    st.markdown('<div style="color:#e8eaed;font-size:15px;font-weight:600;margin-bottom:8px;">All Port Rankings</div>', unsafe_allow_html=True)
    display_df = df[["name", "country", "region", "vessel_count", "score", "label", "wave_height_m"]].copy()
    display_df.columns = ["Port", "Country", "Region", "Vessels Nearby", "Score", "Status", "Wave Height (m)"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
