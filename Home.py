import json
import os
import streamlit as st
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

# ── Load data ─────────────────────────────────────────────────────────
with st.spinner("Loading live intelligence feeds..."):
    vessels         = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)
    bdi             = get_bdi()

df_cong    = pd.DataFrame(congestion_data)
cong_map   = {c["name"]: c for c in congestion_data}
vessel_age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)

critical_n = int((df_cong["score"] >= 86).sum()) if not df_cong.empty else 0
high_n     = int(((df_cong["score"] >= 61) & (df_cong["score"] < 86)).sum()) if not df_cong.empty else 0
alert_count = int((df_cong["score"] >= 60).sum()) + (1 if bdi.get("trend") == "rising" else 0)
alert_cost  = round(sum(
    next((p["capacity_baseline"] for p in ports if p["name"] == row["name"]), 30)
    * row["score"] / 100 * 0.35
    for _, row in df_cong[df_cong["score"] >= 60].iterrows()
), 0)

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

age_str = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching..."
st.markdown(
    f'<div style="display:flex;gap:24px;padding:8px 14px;background:#1a1f2e;border:1px solid #263044;'
    f'border-radius:8px;margin-bottom:24px;flex-wrap:wrap;">'
    f'<span style="color:#5a6a7e;font-size:12px">🛰 <b style="color:#a0aab4">AIS</b> · {age_str}</span>'
    f'<span style="color:#5a6a7e;font-size:12px">🌊 <b style="color:#a0aab4">Marine Weather</b> · Open-Meteo (3h cache)</span>'
    f'<span style="color:#5a6a7e;font-size:12px">📈 <b style="color:#a0aab4">BDI</b> · {bdi.get("value","N/A")} ({bdi.get("trend","N/A")} trend, daily)</span>'
    f'<span style="color:#5a6a7e;font-size:12px">🗺 <b style="color:#a0aab4">Ports Monitored</b> · {len(ports)}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── KPI row — uniform fixed-height cards ─────────────────────────────
def kpi_card(label: str, value: str, sub: str, sub_color: str = "#6b7fa3") -> str:
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;'
        f'padding:16px 18px;height:96px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{label}</div>'
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{sub_color};font-size:12px">{sub}</div>'
        f'</div>'
    )

bdi_chg     = bdi.get("change_pct_1d") or 0
bdi_color   = "#ef5350" if bdi_chg > 0 else "#4caf50" if bdi_chg < 0 else "#6b7fa3"
crit_color  = "#ef5350" if critical_n > 0 else "#4caf50"
alert_color = "#ef5350" if alert_count > 3 else "#ffb74d" if alert_count > 0 else "#4caf50"

c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(kpi_card("Vessels Tracked",  f"{len(vessels):,}",      f"across {len(ports)} ports"),          unsafe_allow_html=True)
c2.markdown(kpi_card("Critical Ports",   str(critical_n),           f"{high_n} high risk", crit_color),    unsafe_allow_html=True)
c3.markdown(kpi_card("Active Alerts",    str(alert_count),          f"${alert_cost:.0f}M exposure", alert_color), unsafe_allow_html=True)
c4.markdown(kpi_card("BDI",             str(bdi.get("value","—")), f"{bdi_chg:+.1f}% today", bdi_color),  unsafe_allow_html=True)
c5.markdown(kpi_card("BDI Trend",        bdi.get("trend","—").upper(), "freight rate direction"),           unsafe_allow_html=True)

st.divider()

# ── Regional shipping delay risk ──────────────────────────────────────
st.markdown(
    '<div style="margin-bottom:4px;">'
    '<span style="color:#e8eaed;font-size:16px;font-weight:700">Shipping Delay Risk by Region</span>'
    '</div>'
    '<div style="color:#5a6a7e;font-size:12px;margin-bottom:16px;">'
    'Probability of port-related shipping delays for goods <em>originating</em> from each region. '
    'Score = export port congestion (60%) + marine weather severity at key ports (30%) + BDI freight pressure (10%).'
    '</div>',
    unsafe_allow_html=True,
)

# Group ports by region and compute regional score
regions_data: dict = {}
for port in ports:
    r = port["region"]
    if r not in regions_data:
        regions_data[r] = []
    regions_data[r].append(port)

def region_delay_risk(region_ports: list, bdi: dict) -> dict:
    scores = [cong_map.get(p["name"], {}).get("score", 0) for p in region_ports]
    if not scores:
        return {"score": 0, "label": "No Data", "color": "#5a6a7e", "top_port": "—", "top_score": 0}
    avg_s  = sum(scores) / len(scores)
    max_s  = max(scores)
    bdi_b  = 10 if bdi.get("trend") == "rising" else 0
    score  = min(100, round(avg_s * 0.6 + max_s * 0.3 + bdi_b * 0.1))
    top_idx = scores.index(max_s)
    top_port = region_ports[top_idx]["name"]
    if score >= 75:   label, color = "HIGH",     "#ef5350"
    elif score >= 50: label, color = "ELEVATED", "#ffb74d"
    elif score >= 25: label, color = "MODERATE", "#00d4ff"
    else:             label, color = "NORMAL",   "#4caf50"
    return {"score": score, "label": label, "color": color,
            "top_port": top_port, "top_score": int(max_s), "port_count": len(region_ports)}

region_results = {r: region_delay_risk(ps, bdi) for r, ps in regions_data.items()}
sorted_regions = sorted(region_results.items(), key=lambda x: x[1]["score"], reverse=True)

# Render as uniform cards — 3 per row
rows = [sorted_regions[i:i+3] for i in range(0, len(sorted_regions), 3)]
for row in rows:
    cols = st.columns(3)
    for col, (region, data) in zip(cols, row):
        c = data["color"]
        col.markdown(
            f'<div style="background:#1a1f2e;border:1px solid #263044;border-left:4px solid {c};'
            f'border-radius:0 10px 10px 0;padding:16px 18px;height:130px;'
            f'display:flex;flex-direction:column;justify-content:space-between;">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
            f'  <span style="color:#e8eaed;font-size:14px;font-weight:700">{region}</span>'
            f'  <span style="background:{c}22;color:{c};padding:2px 9px;border-radius:12px;'
            f'         font-size:11px;font-weight:700">{data["label"]}</span>'
            f'</div>'
            f'<div style="color:{c};font-size:28px;font-weight:800;line-height:1">'
            f'  {data["score"]}<span style="color:#5a6a7e;font-size:13px">/100</span>'
            f'</div>'
            f'<div style="color:#5a6a7e;font-size:12px">'
            f'  Worst port: <span style="color:#a0aab4">{data["top_port"]}</span> '
            f'  ({data["top_score"]}/100) · {data["port_count"]} ports'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ── Bottom section: highlights (left) + port watch (right) ───────────
highlights_col, watch_col = st.columns([3, 1])

with highlights_col:
    st.markdown('<div style="color:#e8eaed;font-size:16px;font-weight:700;margin-bottom:12px;">Current Highlights</div>', unsafe_allow_html=True)

    top_port    = df_cong.iloc[0] if not df_cong.empty else None
    country_scores: dict = {}
    for port in ports:
        c = cong_map.get(port["name"], {})
        sc = c.get("score", 0)
        if port["country"] not in country_scores or sc > country_scores[port["country"]]["score"]:
            country_scores[port["country"]] = {"score": sc, "port": port["name"]}
    top_country = max(country_scores.items(), key=lambda x: x[1]["score"]) if country_scores else None

    spotlight_items = []
    if top_port is not None:
        lc = {"Clear":"#4caf50","Moderate":"#ffb74d","High":"#ef5350","Critical":"#b71c1c"}.get(str(top_port.get("label","")),"#a0aab4")
        spotlight_items.append(("Most Congested Port",
            f"<b style='color:{lc}'>{top_port['name']}</b> is at {int(top_port['score'])}/100 "
            f"({top_port['label']}). Vessels waiting to berth are contributing to longer loading times.",
            "See full rankings in Port Congestion", lc))
    if top_country:
        country, data = top_country
        lc2 = "#b71c1c" if data["score"] >= 86 else "#ef5350" if data["score"] >= 61 else "#ffb74d"
        spotlight_items.append(("Highest Supplier Exposure",
            f"<b style='color:{lc2}'>{country}</b> — export port {data['port']} scoring "
            f"{data['score']}/100. Suppliers in this country face elevated shipment risk.",
            "Full country breakdown in Supplier Risk", lc2))
    bdi_c = "#ef5350" if bdi.get("trend") == "rising" else "#4caf50"
    spotlight_items.append(("Freight Cost Pressure",
        f"Baltic Dry Index at <b style='color:{bdi_c}'>{bdi.get('value','N/A')}</b>, "
        f"{bdi.get('trend','N/A')} trend ({bdi_chg:+.1f}% today). "
        f"{'Rising BDI adds 0.5 days to average route delay estimates.' if bdi.get('trend')=='rising' else 'Stable BDI — no freight cost premium on delay estimates.'}",
        "Route delay estimates in Delay Forecast", bdi_c))
    spotlight_items.append(("Active Disruption Alerts",
        f"<b style='color:#ef5350'>{alert_count} active alerts</b> with an estimated "
        f"<b style='color:#ef5350'>${alert_cost:.0f}M</b> total cost exposure across affected supply lanes.",
        "Full alert feed and recommendations in Risk Alerts", "#ef5350"))

    hl_inner = st.columns(2)
    for i, (title, body, link, accent) in enumerate(spotlight_items):
        hl_inner[i % 2].markdown(
            f'<div style="background:#1a1f2e;border:1px solid #263044;border-left:3px solid {accent};'
            f'border-radius:0 8px 8px 0;padding:14px 16px;margin-bottom:10px;height:120px;'
            f'display:flex;flex-direction:column;justify-content:space-between;">'
            f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{title}</div>'
            f'<div style="color:#a0aab4;font-size:13px;line-height:1.5">{body}</div>'
            f'<div style="color:#00d4ff;font-size:12px">{link}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

with watch_col:
    st.markdown('<div style="color:#e8eaed;font-size:16px;font-weight:700;margin-bottom:12px;">Port Watch</div>', unsafe_allow_html=True)
    lc_map = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}
    top8 = df_cong.head(8) if not df_cong.empty else pd.DataFrame()
    for _, row in top8.iterrows():
        lc = lc_map.get(row.get("label", ""), "#a0aab4")
        watch_col.markdown(
            f'<div style="display:flex;align-items:center;padding:8px 10px;margin-bottom:5px;'
            f'background:#1a1f2e;border-radius:7px;border:1px solid #263044;border-left:3px solid {lc};">'
            f'<div style="flex:1;color:#e8eaed;font-size:12px;font-weight:600;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'<div style="color:{lc};font-size:13px;font-weight:700;flex-shrink:0;margin-left:8px">{int(row["score"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    if not df_cong.empty:
        watch_col.markdown(
            f'<div style="color:#5a6a7e;font-size:11px;margin-top:6px;padding:0 4px">'
            f'{len(df_cong)} ports scored · {critical_n} critical · {high_n} high risk'
            f'</div>',
            unsafe_allow_html=True,
        )
