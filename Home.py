import json
import os
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from db import cache
from components.styles import inject_global_css, navbar

load_dotenv()

st.set_page_config(
    page_title="Dashboard | CargoPulse",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_global_css()
navbar(current="Dashboard")

PORTS_PATH = os.path.join(os.path.dirname(__file__), "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

# ── Load data ──────────────────────────────────────────────────────────
with st.spinner("Loading live intelligence feeds..."):
    vessels         = aisstream.get_vessels(bounding_boxes)
    congestion_data = cong_svc.get_all_port_congestion(vessels)
    bdi             = get_bdi()

df_cong    = pd.DataFrame(congestion_data).sort_values("score", ascending=False) if congestion_data else pd.DataFrame()
vessel_age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)

critical_n  = int((df_cong["score"] >= 86).sum()) if not df_cong.empty else 0
high_n      = int(((df_cong["score"] >= 61) & (df_cong["score"] < 86)).sum()) if not df_cong.empty else 0
alert_count = int((df_cong["score"] >= 60).sum()) + (1 if bdi.get("trend") == "rising" else 0)
alert_cost  = round(sum(
    next((p["capacity_baseline"] for p in ports if p["name"] == row["name"]), 30)
    * row["score"] / 100 * 0.35
    for _, row in df_cong[df_cong["score"] >= 60].iterrows()
), 0) if not df_cong.empty else 0
bdi_chg     = bdi.get("change_pct_1d") or 0

# ── Status bar ─────────────────────────────────────────────────────────
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
age_str      = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching..."
conn_color   = "#4caf50" if is_connected else "#ef5350"
live_color   = "#4caf50" if is_live else "#ffb74d"

st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;'
    f'padding:7px 14px;background:#1a1f2e;border:1px solid #263044;'
    f'border-radius:8px;margin-bottom:14px;flex-wrap:wrap;gap:8px;">'
    f'<div style="display:flex;gap:20px;flex-wrap:wrap;">'
    f'<span style="color:#5a6a7e;font-size:12px">AIS · <b style="color:#a0aab4">{age_str}</b></span>'
    f'<span style="color:#5a6a7e;font-size:12px">Weather · <b style="color:#a0aab4">Open-Meteo (3h cache)</b></span>'
    f'<span style="color:#5a6a7e;font-size:12px">BDI · <b style="color:#a0aab4">{bdi.get("value","N/A")} ({bdi.get("trend","N/A")})</b></span>'
    f'<span style="color:#5a6a7e;font-size:12px">Ports · <b style="color:#a0aab4">{len(ports)}</b></span>'
    f'</div>'
    f'<div style="display:flex;gap:14px;align-items:center;">'
    f'<div style="display:flex;align-items:center;gap:5px;">'
    f'<div style="width:7px;height:7px;border-radius:50%;background:{conn_color};box-shadow:0 0 5px {conn_color}"></div>'
    f'<span style="color:#a0aab4;font-size:12px">Connected</span>'
    f'</div>'
    f'<div style="display:flex;align-items:center;gap:5px;">'
    f'<div style="width:7px;height:7px;border-radius:50%;background:{live_color};box-shadow:0 0 5px {live_color}"></div>'
    f'<span style="color:#a0aab4;font-size:12px">Live</span>'
    f'</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── KPI row ────────────────────────────────────────────────────────────
def _kpi(label, value, sub, sub_color="#6b7fa3", border_color=None):
    bl = f"border-left:3px solid {border_color};" if border_color else ""
    br = "0 10px 10px 0" if border_color else "10px"
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;{bl}'
        f'border-radius:{br};padding:14px 18px;height:88px;'
        f'display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{label}</div>'
        f'<div style="color:#e8eaed;font-size:24px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{sub_color};font-size:12px">{sub}</div>'
        f'</div>'
    )

bdi_color   = "#ef5350" if bdi_chg > 0 else "#4caf50" if bdi_chg < 0 else "#6b7fa3"
crit_color  = "#ef5350" if critical_n > 0 else "#4caf50"
alert_color = "#ef5350" if alert_count > 3 else "#ffb74d" if alert_count > 0 else "#4caf50"

c1, c2, c3, c4 = st.columns(4)
c1.markdown(_kpi("Vessels Tracked",  f"{len(vessels):,}",       f"across {len(ports)} ports"),                                  unsafe_allow_html=True)
c2.markdown(_kpi("Critical Ports",   str(critical_n),            f"{high_n} high risk",          crit_color,  "#ef5350" if critical_n > 0 else None),  unsafe_allow_html=True)
c3.markdown(_kpi("Active Alerts",    str(alert_count),           f"${alert_cost:.0f}M exposure", alert_color, "#ef5350" if alert_count > 0 else None),  unsafe_allow_html=True)
c4.markdown(_kpi("BDI",             str(bdi.get("value", "—")), f"{bdi_chg:+.1f}% · {bdi.get('trend','—').upper()}",          bdi_color),              unsafe_allow_html=True)

st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)

# ── Main: world map (left) + ports & alerts (right) ────────────────────
map_col, right_col = st.columns([3, 2])

LC = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}

with map_col:
    st.markdown(
        '<div style="color:#e8eaed;font-size:13px;font-weight:600;margin-bottom:6px;">'
        'Port Congestion Map</div>',
        unsafe_allow_html=True,
    )
    fig = go.Figure()
    if not df_cong.empty:
        for label, color in LC.items():
            sub = df_cong[df_cong["label"] == label]
            if sub.empty:
                continue
            fig.add_trace(go.Scattergeo(
                lat=sub["lat"].tolist(),
                lon=sub["lon"].tolist(),
                mode="markers",
                name=label,
                marker=dict(
                    size=sub["score"].apply(lambda s: max(5, s / 7 + 5)).tolist(),
                    color=color,
                    opacity=0.85,
                    line=dict(width=0),
                ),
                showlegend=True,
                hovertext=sub.apply(
                    lambda r: f"<b>{r['name']}</b><br>Score: {r['score']}/100 — {r['label']}<br>Vessels: {r['vessel_count']}",
                    axis=1,
                ).tolist(),
                hovertemplate="%{hovertext}<extra></extra>",
            ))
    fig.update_layout(
        geo=dict(
            projection_type="natural earth",
            showland=True,     landcolor="#1a1f2e",
            showocean=True,    oceancolor="#0d1218",
            showlakes=False,
            showcountries=True, countrycolor="#263044",
            showframe=False,   bgcolor="#0f1117",
        ),
        paper_bgcolor="#0f1117",
        margin=dict(l=0, r=0, t=0, b=0),
        height=430,
        legend=dict(
            bgcolor="#1a1f2e", bordercolor="#263044",
            font=dict(color="#a0aab4", size=11),
            orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.0,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

with right_col:
    # ── Top Congested Ports ───────────────────────────────────────────
    st.markdown(
        '<div style="color:#e8eaed;font-size:13px;font-weight:600;margin-bottom:8px;">'
        'Top Congested Ports</div>',
        unsafe_allow_html=True,
    )
    for _, row in df_cong.head(5).iterrows():
        lc = LC.get(row.get("label", ""), "#a0aab4")
        st.markdown(
            f'<div style="display:flex;align-items:center;padding:8px 12px;margin-bottom:5px;'
            f'background:#1a1f2e;border-radius:8px;border:1px solid #263044;border-left:3px solid {lc};">'
            f'<div style="flex:1;min-width:0;">'
            f'  <div style="color:#e8eaed;font-size:13px;font-weight:600;'
            f'       white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'  <div style="color:#5a6a7e;font-size:11px">{row["country"]} · {row["vessel_count"]} vessels</div>'
            f'</div>'
            f'<div style="text-align:right;flex-shrink:0;margin-left:10px;">'
            f'  <span style="color:{lc};font-size:17px;font-weight:800">{row["score"]}</span>'
            f'  <span style="color:#5a6a7e;font-size:11px">/100</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)

    # ── Live Alerts ───────────────────────────────────────────────────
    st.markdown(
        '<div style="color:#e8eaed;font-size:13px;font-weight:600;margin-bottom:8px;">'
        'Live Alerts</div>',
        unsafe_allow_html=True,
    )

    alerts: list[tuple] = []
    if not df_cong.empty:
        for _, row in df_cong[df_cong["score"] >= 60].head(3).iterrows():
            sev   = "CRITICAL" if row["score"] >= 86 else "HIGH"
            color = "#b71c1c"  if sev == "CRITICAL"  else "#ef5350"
            alerts.append((sev, row["name"], f"Congestion {row['score']}/100 · {row['vessel_count']} vessels nearby", color))
    if bdi.get("trend") == "rising":
        alerts.append(("WATCH", "Rising BDI — Freight Pressure", f"Index {bdi.get('value','N/A')} · {bdi_chg:+.1f}% today", "#ffb74d"))
    if not alerts:
        alerts.append(("CLEAR", "No Active Alerts", "All monitored ports are below risk threshold", "#4caf50"))

    for sev, title, body, color in alerts[:4]:
        st.markdown(
            f'<div style="background:{color}18;border:1px solid {color}44;'
            f'border-left:3px solid {color};border-radius:0 8px 8px 0;'
            f'padding:10px 12px;margin-bottom:6px;">'
            f'<div style="color:{color};font-size:10px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">{sev}</div>'
            f'<div style="color:#e8eaed;font-size:13px;font-weight:600">{title}</div>'
            f'<div style="color:#6b7fa3;font-size:12px;margin-top:2px">{body}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
