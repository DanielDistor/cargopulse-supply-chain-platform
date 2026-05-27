import json
import os
import hashlib
import datetime
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from db import cache
from components.styles import inject_global_css

load_dotenv()

st.set_page_config(
    page_title="CargoPulse | Supply Chain Intelligence",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()

PORTS_PATH = os.path.join(os.path.dirname(__file__), "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

# ── Load all data ─────────────────────────────────────────────────────
with st.spinner("Loading live intelligence feeds..."):
    vessels        = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)
    bdi            = get_bdi()

df_cong = pd.DataFrame(congestion_data)
vessel_age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)

# ── Connection status ─────────────────────────────────────────────────
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
conn_color   = "#4caf50" if is_connected else "#ef5350"
live_color   = "#4caf50" if is_live      else "#ffb74d"

st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
    <div>
        <div style="font-size:28px;font-weight:800;color:#e8eaed;margin-bottom:6px;">🚢 CargoPulse</div>
        <div style="color:#6b7fa3;font-size:14px">
            Supply chain risk intelligence — live data from AISstream, Open-Meteo Marine, and Baltic Dry Index.
        </div>
    </div>
    <div style="display:flex;gap:20px;align-items:center;padding-top:6px;flex-shrink:0;">
        <div style="display:flex;align-items:center;gap:7px;">
            <div style="width:9px;height:9px;border-radius:50%;background:{conn_color};box-shadow:0 0 8px {conn_color}"></div>
            <span style="color:#a0aab4;font-size:13px;font-weight:600">Connected</span>
        </div>
        <div style="display:flex;align-items:center;gap:7px;">
            <div style="width:9px;height:9px;border-radius:50%;background:{live_color};box-shadow:0 0 8px {live_color}"></div>
            <span style="color:#a0aab4;font-size:13px;font-weight:600">Live Monitoring</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Data freshness bar
age_str = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching..."
bdi_val = bdi.get("value", "N/A")
st.markdown(
    f'<div style="display:flex;gap:24px;padding:8px 14px;background:#1a1f2e;border:1px solid #263044;'
    f'border-radius:8px;margin-bottom:20px;flex-wrap:wrap;">'
    f'<span style="color:#5a6a7e;font-size:12px">🛰 <b style="color:#a0aab4">AIS</b> · {age_str}</span>'
    f'<span style="color:#5a6a7e;font-size:12px">🌊 <b style="color:#a0aab4">Marine Weather</b> · Open-Meteo (3h cache)</span>'
    f'<span style="color:#5a6a7e;font-size:12px">📈 <b style="color:#a0aab4">BDI</b> · {bdi_val} ({bdi.get("trend", "N/A")} trend, daily)</span>'
    f'<span style="color:#5a6a7e;font-size:12px">🗺 <b style="color:#a0aab4">Ports Monitored</b> · {len(ports)}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Composite global risk score ───────────────────────────────────────
avg_cong   = df_cong["score"].mean() if not df_cong.empty else 0
max_cong   = df_cong["score"].max()  if not df_cong.empty else 0
bdi_factor = 15 if bdi.get("trend") == "rising" else 0
critical_n = int((df_cong["score"] >= 86).sum()) if not df_cong.empty else 0
high_n     = int(((df_cong["score"] >= 61) & (df_cong["score"] < 86)).sum()) if not df_cong.empty else 0

global_score = min(100, round(avg_cong * 0.5 + max_cong * 0.3 + bdi_factor + critical_n * 1.5))

if global_score >= 75:
    risk_label, risk_color = "HIGH RISK",    "#ef5350"
elif global_score >= 50:
    risk_label, risk_color = "ELEVATED",     "#ffb74d"
elif global_score >= 25:
    risk_label, risk_color = "MODERATE",     "#00d4ff"
else:
    risk_label, risk_color = "NORMAL",       "#4caf50"

# ── Layout: gauge left, spotlight cards right ─────────────────────────
gauge_col, cards_col = st.columns([1, 2])

with gauge_col:
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=global_score,
        title={"text": "Global Risk Score", "font": {"color": "#a0aab4", "size": 14}},
        number={"font": {"color": risk_color, "size": 48}, "suffix": "/100"},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#5a6a7e", "tickfont": {"color": "#5a6a7e"}},
            "bar":  {"color": risk_color, "thickness": 0.25},
            "bgcolor": "#1a1f2e",
            "bordercolor": "#263044",
            "steps": [
                {"range": [0,  25],  "color": "#0d2818"},
                {"range": [25, 50],  "color": "#0d2020"},
                {"range": [50, 75],  "color": "#2a1a0a"},
                {"range": [75, 100], "color": "#2a0a0a"},
            ],
            "threshold": {"line": {"color": risk_color, "width": 3}, "value": global_score},
        },
    ))
    fig_gauge.update_layout(
        height=260, margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="#1a1f2e", font_color="#a0aab4",
    )
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown(
        f'<div style="text-align:center;margin-top:-10px;">'
        f'<span style="background:{risk_color}22;color:{risk_color};padding:4px 16px;'
        f'border-radius:20px;font-size:13px;font-weight:700;border:1px solid {risk_color}44">'
        f'{risk_label}</span></div>',
        unsafe_allow_html=True,
    )

with cards_col:
    # Spotlight: biggest signal from each dimension
    top_port    = df_cong.iloc[0] if not df_cong.empty else None
    country_scores = {}
    for port in ports:
        cong = df_cong[df_cong["name"] == port["name"]]
        if not cong.empty:
            sc = int(cong.iloc[0]["score"])
            if port["country"] not in country_scores or sc > country_scores[port["country"]]["score"]:
                country_scores[port["country"]] = {"score": sc, "port": port["name"]}
    top_country = max(country_scores.items(), key=lambda x: x[1]["score"]) if country_scores else None

    def _h(s): return int(hashlib.md5(s.encode()).hexdigest(), 16)

    # Alert count from congestion threshold
    alert_count = int((df_cong["score"] >= 60).sum()) + (1 if bdi.get("trend") == "rising" else 0)
    alert_cost  = round(sum(
        port_map_local["capacity_baseline"] * row["score"] / 100 * 0.35
        for _, row in df_cong[df_cong["score"] >= 60].iterrows()
        for port_map_local in [next((p for p in ports if p["name"] == row["name"]), {"capacity_baseline": 30})]
    ), 0)

    spotlight_items = []
    if top_port is not None:
        lc = {"Clear":"#4caf50","Moderate":"#ffb74d","High":"#ef5350","Critical":"#b71c1c"}.get(top_port["label"],"#a0aab4")
        spotlight_items.append(("📊 Most Congested Port",
            f"<span style='color:{lc};font-weight:700'>{top_port['name']}</span> — "
            f"<span style='color:{lc}'>{int(top_port['score'])}/100 · {top_port['label']}</span>",
            "→ Port Congestion"))
    if top_country:
        country, data = top_country
        lc2 = "#b71c1c" if data["score"] >= 86 else "#ef5350" if data["score"] >= 61 else "#ffb74d"
        spotlight_items.append(("⚠️ Highest Risk Country",
            f"<span style='color:{lc2};font-weight:700'>{country}</span> — "
            f"<span style='color:{lc2}'>composite risk {data['score']}/100 via {data['port']}</span>",
            "→ Supplier Risk"))
    bdi_c = "#ef5350" if bdi.get("trend") == "rising" else "#4caf50"
    spotlight_items.append(("📈 Freight Market",
        f"<span style='color:{bdi_c};font-weight:700'>BDI {bdi.get('value','N/A')}</span> — "
        f"<span style='color:{bdi_c}'>{bdi.get('trend','N/A')} trend · {bdi.get('change_pct_1d') or 0:.1f}% today</span>",
        "→ Delay Forecast"))
    spotlight_items.append(("🚨 Active Risk Alerts",
        f"<span style='color:#ef5350;font-weight:700'>{alert_count} alerts</span> — "
        f"<span style='color:#ef5350'>estimated ${alert_cost:.0f}M total exposure</span>",
        "→ Risk Alerts"))

    for title, body, link in spotlight_items:
        st.markdown(
            f'<div style="background:#1a1f2e;border:1px solid #263044;border-left:3px solid #00d4ff;'
            f'border-radius:0 8px 8px 0;padding:14px 16px;margin-bottom:10px;">'
            f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px">{title}</div>'
            f'<div style="font-size:14px;margin-bottom:4px">{body}</div>'
            f'<div style="color:#00d4ff;font-size:12px">{link}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ── Platform summary KPIs ─────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Vessels Tracked",    f"{len(vessels):,}")
k2.metric("Ports Monitored",    len(ports))
k3.metric("Critical Ports",     critical_n,  delta=f"{high_n} high risk")
k4.metric("Active Alerts",      alert_count)
k5.metric("BDI",                bdi.get("value", "N/A"), delta=f"{bdi.get('change_pct_1d') or 0:.1f}% today")
