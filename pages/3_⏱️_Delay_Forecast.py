import json
import os
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc, weather as weather_svc
from services.shipping_rates import get_bdi
from components.styles import inject_global_css, page_header

load_dotenv()

st.set_page_config(page_title="Delay Forecast | CargoPulse", layout="wide")
inject_global_css()
page_header(
    "⏱️ Shipment Delay Forecast",
    "Rule-based delay estimates using live congestion, marine weather, and Baltic Dry Index. Use as one signal among many."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

port_names = [p["name"] for p in ports]
port_map = {p["name"]: p for p in ports}

# Pre-defined top global trade routes
TOP_ROUTES = [
    ("Shanghai", "Los Angeles"),
    ("Shanghai", "Rotterdam"),
    ("Singapore", "Rotterdam"),
    ("Ningbo-Zhoushan", "Long Beach"),
    ("Busan", "Los Angeles"),
    ("Shanghai", "Hamburg"),
    ("Singapore", "Los Angeles"),
    ("Guangzhou", "Rotterdam"),
    ("Dubai (Jebel Ali)", "Rotterdam"),
    ("Tokyo", "Los Angeles"),
    ("Shanghai", "New York / NJ"),
    ("Mumbai (JNPT)", "Rotterdam"),
    ("Santos", "Rotterdam"),
    ("Busan", "Rotterdam"),
    ("Singapore", "Hamburg"),
]


def compute_delay(origin: str, destination: str, cong_map: dict, port_map: dict, bdi: dict) -> dict:
    origin_data = cong_map.get(origin, {})
    dest_data = cong_map.get(destination, {})
    origin_port = port_map.get(origin, {})
    wave_h = weather_svc.get_marine_weather(origin_port.get("lat", 0), origin_port.get("lon", 0)).get("wave_height_m")
    baseline = origin_port.get("avg_delay_days", 2)
    congestion_delay = (origin_data.get("score", 0) / 100) * 3.0
    weather_delay = (weather_svc.weather_penalty(wave_h) - 1.0) * 4.0
    bdi_delay = 0.5 if bdi.get("trend") == "rising" else 0.0
    dest_delay = (dest_data.get("score", 0) / 100) * 1.5
    total = min(round(baseline + congestion_delay + weather_delay + bdi_delay + dest_delay, 1), 7.0)
    return {
        "origin": origin,
        "destination": destination,
        "delay": total,
        "status": "⚫ Critical" if total >= 5 else "🔴 High" if total >= 3.5 else "🟡 Moderate" if total >= 2 else "🟢 Low",
        "origin_score": origin_data.get("score", 0),
        "dest_score": dest_data.get("score", 0),
    }


tab1, tab2 = st.tabs(["🔍 Route Calculator", "🌐 Global Trade Routes"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        origin = st.selectbox("Origin port", port_names, index=port_names.index("Shanghai"))
    with col2:
        destination = st.selectbox("Destination port", port_names, index=port_names.index("Los Angeles"))

    if origin == destination:
        st.warning("Origin and destination must be different ports.")
        st.stop()

    if st.button("Calculate Delay Forecast", type="primary"):
        with st.spinner("Analysing route..."):
            bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]
            vessels = aisstream.get_vessels(bounding_boxes)
            all_congestion = cong_svc.get_all_port_congestion(vessels)
            cong_map = {c["name"]: c for c in all_congestion}
            origin_data = cong_map.get(origin, {})
            dest_data = cong_map.get(destination, {})
            origin_port = port_map[origin]
            origin_score = origin_data.get("score", 0)
            dest_score = dest_data.get("score", 0)
            wave_h = weather_svc.get_marine_weather(origin_port["lat"], origin_port["lon"]).get("wave_height_m")
            bdi = get_bdi()
            baseline = origin_port.get("avg_delay_days", 2)
            congestion_delay = (origin_score / 100) * 3.0
            weather_delay = (weather_svc.weather_penalty(wave_h) - 1.0) * 4.0
            bdi_delay = 0.5 if bdi.get("trend") == "rising" else 0.0
            dest_delay = (dest_score / 100) * 1.5
            total_delay = min(round(baseline + congestion_delay + weather_delay + bdi_delay + dest_delay, 1), 7.0)
            confidence = max(40, 90 - int(total_delay * 5))

        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Estimated Delay", f"+{total_delay} days")
        r2.metric("Forecast Confidence", f"{confidence}%")
        r3.metric("Historical Baseline", f"{baseline} days", help="Average delay from this origin port.")

        st.divider()
        left, right = st.columns([3, 2])

        with left:
            st.subheader("What is driving this forecast?")
            drivers = [
                ("Historical baseline", baseline, "#4a9eff"),
                ("Origin congestion", round(congestion_delay, 2), "#ef5350"),
                ("Marine weather", round(weather_delay, 2), "#ffb74d"),
                ("BDI rate pressure", bdi_delay, "#ce93d8"),
                ("Destination congestion", round(dest_delay, 2), "#f48fb1"),
            ]
            fig = go.Figure(go.Bar(
                x=[d[1] for d in drivers],
                y=[d[0] for d in drivers],
                orientation="h",
                marker_color=[d[2] for d in drivers],
            ))
            fig.update_layout(
                title="Days added by each factor",
                xaxis_title="Days",
                height=300,
                margin=dict(l=10, r=10, t=50, b=10),
                paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
                xaxis=dict(gridcolor="#1e2736"), yaxis=dict(gridcolor="#1e2736"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with right:
            st.subheader("Baltic Dry Index (30 days)")
            bdi_hist = bdi.get("history", [])
            bdi_dates = bdi.get("dates", [])
            if bdi_hist and bdi_dates:
                bdi_df = pd.DataFrame({"Date": bdi_dates[-30:], "BDI": bdi_hist[-30:]})
                fig_bdi = px.line(bdi_df, x="Date", y="BDI", height=300)
                fig_bdi.update_traces(line_color="#00d4ff", line_width=2)
                fig_bdi.update_layout(
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
                    xaxis=dict(gridcolor="#1e2736", tickangle=-30),
                    yaxis=dict(gridcolor="#1e2736"),
                    title=f"Current: {bdi.get('value', 'N/A')} ({bdi.get('trend', 'N/A')} trend)",
                    title_font_color="#e8eaed",
                )
                st.plotly_chart(fig_bdi, use_container_width=True)
            else:
                st.info("BDI history not available — check yfinance connection.")

        with st.expander("Full factor breakdown"):
            st.write(f"Origin congestion: {origin_score}/100 ({origin_data.get('label','N/A')})")
            st.write(f"Destination congestion: {dest_score}/100 ({dest_data.get('label','N/A')})")
            st.write(f"Wave height at origin: {wave_h if wave_h is not None else 'N/A'} m")
            st.write(f"BDI: {bdi.get('value','N/A')} (trend: {bdi.get('trend','N/A')})")

with tab2:
    st.subheader("Top 15 Global Trade Routes — Live Delay Estimates")
    st.caption("Delay estimates computed live using current congestion scores for each origin and destination port.")

    with st.spinner("Calculating all routes..."):
        bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]
        vessels = aisstream.get_vessels(bounding_boxes)
        all_congestion = cong_svc.get_all_port_congestion(vessels)
        cong_map_global = {c["name"]: c for c in all_congestion}
        bdi_global = get_bdi()

    route_results = []
    for orig, dest in TOP_ROUTES:
        if orig in port_map and dest in port_map:
            result = compute_delay(orig, dest, cong_map_global, port_map, bdi_global)
            route_results.append(result)

    routes_df = pd.DataFrame(route_results).sort_values("delay", ascending=False)

    # Heatmap-style bar chart
    fig_routes = px.bar(
        routes_df,
        x="delay",
        y=routes_df.apply(lambda r: f"{r['origin']} → {r['destination']}", axis=1),
        orientation="h",
        color="delay",
        color_continuous_scale=["#4caf50", "#ffb74d", "#ef5350", "#b71c1c"],
        range_color=(0, 7),
        labels={"x": "Estimated delay (days)", "y": "Trade Route"},
        height=520,
    )
    fig_routes.update_layout(
        paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e", font_color="#a0aab4",
        xaxis=dict(gridcolor="#1e2736", title="Estimated delay (days)"),
        yaxis=dict(gridcolor="#1e2736"),
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_routes, use_container_width=True)

    # Route table
    display_routes = routes_df[["origin", "destination", "delay", "status", "origin_score", "dest_score"]].copy()
    display_routes.columns = ["Origin", "Destination", "Est. Delay (days)", "Risk Level", "Origin Congestion", "Dest Congestion"]
    st.dataframe(display_routes, use_container_width=True, hide_index=True)
