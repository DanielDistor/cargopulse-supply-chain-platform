import json
import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc, weather as weather_svc
from services.shipping_rates import get_bdi
from components.styles import inject_global_css, page_header

load_dotenv()

st.set_page_config(page_title="Supplier Risk | CargoPulse", layout="wide")
inject_global_css()
page_header(
    "⚠️ Supplier Region Risk",
    "Composite risk score per country from export port congestion (60%), marine weather (30%), and BDI momentum (10%)."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]


def risk_label(score: int) -> str:
    if score <= 25: return "LOW"
    if score <= 50: return "MEDIUM"
    if score <= 75: return "HIGH"
    return "CRITICAL"


def risk_color(score: int) -> str:
    if score <= 25: return "#4caf50"
    if score <= 50: return "#ffb74d"
    if score <= 75: return "#ef5350"
    return "#b71c1c"


with st.spinner("Computing regional risk scores..."):
    vessels = aisstream.get_vessels(bounding_boxes)
    all_congestion = cong_svc.get_all_port_congestion(vessels)
    bdi = get_bdi()
    cong_map = {c["name"]: c for c in all_congestion}

country_scores = {}
for port in ports:
    cong = cong_map.get(port["name"], {})
    w = weather_svc.get_marine_weather(port["lat"], port["lon"])
    cong_score = cong.get("score", 0)
    wave_penalty = (weather_svc.weather_penalty(w.get("wave_height_m")) - 1.0) * 100
    bdi_penalty = 10 if bdi.get("trend") == "rising" else 0
    composite = min(round((cong_score * 0.6) + (wave_penalty * 0.3) + (bdi_penalty * 0.1)), 100)
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

with st.sidebar:
    st.markdown("### Filters")
    regions = sorted(df["region"].unique())
    selected = st.multiselect("Filter by region", regions, default=regions)
    df = df[df["region"].isin(selected)]

# KPI row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Countries Monitored", len(df))
high_crit = int((df["score"] > 50).sum())
c2.metric("HIGH or CRITICAL", high_crit, delta=f"{high_crit/len(df)*100:.0f}% of monitored" if len(df) else "")
c3.metric("BDI Trend", bdi.get("trend", "N/A").upper(), delta=f"{bdi.get('change_pct_1d') or 0:.1f}% today")
c4.metric("Avg Risk Score", f"{df['score'].mean():.0f} / 100")

st.divider()

tab1, tab2, tab3 = st.tabs(["🗺️ World Heatmap", "🚨 Top At-Risk Countries", "📊 Regional Breakdown"])

with tab1:
    fig_map = px.choropleth(
        df,
        locations="country",
        locationmode="country names",
        color="score",
        color_continuous_scale=["#1a3a2a", "#4caf50", "#ffb74d", "#ef5350", "#b71c1c"],
        range_color=(0, 100),
        hover_data=["label", "worst_port", "congestion_score"],
        title="Supply Chain Risk by Country",
        height=540,
    )
    fig_map.update_layout(
        coloraxis_colorbar=dict(title="Risk Score", tickfont=dict(color="#a0aab4")),
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="#1a1f2e",
        geo=dict(
            bgcolor="#0f1117", lakecolor="#0f1117", landcolor="#1a1f2e",
            showframe=False, showcoastlines=True, coastlinecolor="#263044",
        ),
        title_font_color="#e8eaed",
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.subheader("All Country Rankings")
    display_df = df[["country", "region", "label", "score", "worst_port", "congestion_score", "wave_height_m", "bdi_trend"]].copy()
    display_df.columns = ["Country", "Region", "Risk", "Score", "Key Port", "Port Congestion", "Wave (m)", "BDI"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Highest Risk Countries")
    top_risk = df.head(8)
    cols = st.columns(2)
    for i, (_, row) in enumerate(top_risk.iterrows()):
        with cols[i % 2]:
            border_color = row["color"]
            wave_display = f"{row['wave_height_m']} m" if row["wave_height_m"] is not None else "N/A"
            st.markdown(
                f"""
                <div style="
                    background:linear-gradient(135deg,#1a1f2e,#16202f);
                    border:1px solid #263044;
                    border-left:4px solid {border_color};
                    border-radius:0 10px 10px 0;
                    padding:16px 18px;
                    margin-bottom:12px;
                    height:160px;
                    display:flex;flex-direction:column;justify-content:space-between;
                ">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="color:#e8eaed;font-size:16px;font-weight:700">{row['country']}</span>
                        <span style="background:{border_color};color:{'#0f1117' if row['label']=='LOW' else 'white'};
                            padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700">{row['label']}</span>
                    </div>
                    <div style="color:#6b7fa3;font-size:13px;margin-bottom:10px">{row['region']} · Key port: <strong style="color:#a0aab4">{row['worst_port']}</strong></div>
                    <div style="display:flex;gap:20px;">
                        <div><div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em">Risk Score</div>
                            <div style="color:#e8eaed;font-size:20px;font-weight:800">{row['score']}<span style="color:#5a6a7e;font-size:12px">/100</span></div></div>
                        <div><div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em">Port Congestion</div>
                            <div style="color:#e8eaed;font-size:20px;font-weight:800">{row['congestion_score']}<span style="color:#5a6a7e;font-size:12px">/100</span></div></div>
                        <div><div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em">Wave Height</div>
                            <div style="color:#e8eaed;font-size:20px;font-weight:800">{wave_display}</div></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tab3:
    st.subheader("Risk by Region")
    region_df = df.groupby("region").agg(
        avg_score=("score", "mean"),
        max_score=("score", "max"),
        country_count=("country", "count"),
        high_or_critical=("score", lambda x: (x > 50).sum()),
    ).reset_index().sort_values("avg_score", ascending=True)

    fig_region = go.Figure()
    fig_region.add_trace(go.Bar(
        y=region_df["region"], x=region_df["avg_score"],
        orientation="h", name="Avg Score",
        marker_color="#00d4ff", opacity=0.8,
    ))
    fig_region.add_trace(go.Bar(
        y=region_df["region"], x=region_df["max_score"],
        orientation="h", name="Highest Score",
        marker_color="#ef5350", opacity=0.5,
    ))
    fig_region.update_layout(
        barmode="overlay",
        title="Average vs Highest Risk Score by Region",
        xaxis_title="Score (0–100)",
        height=420,
        paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
        xaxis=dict(gridcolor="#1e2736", range=[0, 100]),
        yaxis=dict(gridcolor="#1e2736"),
        legend=dict(bgcolor="#1a1f2e", bordercolor="#263044"),
        title_font_color="#e8eaed",
    )
    st.plotly_chart(fig_region, use_container_width=True)

    # Concentration table
    region_df["exposure"] = (region_df["high_or_critical"] / region_df["country_count"] * 100).round(1)
    region_display = region_df[["region", "country_count", "avg_score", "max_score", "high_or_critical", "exposure"]].copy()
    region_display.columns = ["Region", "Countries", "Avg Score", "Peak Score", "HIGH/CRITICAL", "% Exposed"]
    region_display = region_display.sort_values("Avg Score", ascending=False)
    st.dataframe(region_display, use_container_width=True, hide_index=True)

    # Country drill-down
    st.divider()
    selected_country = st.selectbox("Inspect a country in detail", df["country"].tolist())
    if selected_country:
        row = df[df["country"] == selected_country].iloc[0]
        r1, r2, r3 = st.columns(3)
        r1.metric("Risk Level", row["label"])
        r2.metric("Composite Score", row["score"])
        r3.metric("Key Export Port", row["worst_port"])
        st.info(
            f"Port congestion at {row['worst_port']} is {row['congestion_score']}/100 (60% weight). "
            f"Wave height is {row['wave_height_m'] if row['wave_height_m'] is not None else 'N/A'} m (30% weight). "
            f"BDI trend is {row['bdi_trend']} (10% weight)."
        )
