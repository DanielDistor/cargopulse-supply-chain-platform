import json
import os
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc, weather as weather_svc
from services.shipping_rates import get_bdi
from components.styles import inject_global_css, page_header

load_dotenv()

st.set_page_config(page_title="Delay Forecast | CargoPulse", layout="wide")

inject_global_css()

page_header(
    "⏱️ Shipment Delay Forecast",
    "Rule-based delay estimate using port congestion, marine weather severity, and Baltic Dry Index trend. Treat this as one signal, not a guarantee."
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

port_names = [p["name"] for p in ports]
port_map = {p["name"]: p for p in ports}

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
        r3.metric("Historical Baseline", f"{baseline} days", help="Average delay at this origin port historically.")

        st.divider()
        st.subheader("What is driving this forecast?")

        drivers = [
            ("Historical baseline", baseline, "#4a9eff"),
            ("Origin port congestion", round(congestion_delay, 2), "#ef5350"),
            ("Marine weather severity", round(weather_delay, 2), "#ffb74d"),
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
            height=320,
            margin=dict(l=10, r=10, t=50, b=10),
            paper_bgcolor="#1a1f2e",
            plot_bgcolor="#1a1f2e",
            font_color="#a0aab4",
            xaxis=dict(gridcolor="#1e2736"),
            yaxis=dict(gridcolor="#1e2736"),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Factor details"):
            st.write(f"Origin congestion score: {origin_score}/100 ({origin_data.get('label','N/A')})")
            st.write(f"Destination congestion score: {dest_score}/100 ({dest_data.get('label','N/A')})")
            st.write(f"Wave height at origin: {wave_h if wave_h is not None else 'N/A'} m")
            st.write(f"Baltic Dry Index: {bdi.get('value','N/A')} (trend: {bdi.get('trend','N/A')})")
