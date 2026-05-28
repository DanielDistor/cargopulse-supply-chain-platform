import json
import os
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from services.news import get_maritime_news
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
bdi_chg = bdi.get("change_pct_1d") or 0

# ── Page header ────────────────────────────────────────────────────────
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
age_str      = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching…"

if is_live:
    status_label, status_color = "System Operational", "#4caf50"
elif is_connected:
    status_label, status_color = "Data Stale",         "#ffb74d"
else:
    status_label, status_color = "Offline",            "#ef5350"

st.markdown(
    f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding-bottom:12px;border-bottom:1px solid #1e2736;">
        <div>
            <div style="color:#e8eaed;font-size:22px;font-weight:800;
                        letter-spacing:-0.02em;line-height:1.2">Supply Chain Intelligence</div>
            <div style="color:#5a6a7e;font-size:13px;margin-top:4px">
                Live port congestion &nbsp;·&nbsp; vessel tracking
                &nbsp;·&nbsp; BDI freight analysis &nbsp;·&nbsp; {len(ports)} ports monitored
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:14px;flex-shrink:0;">
            <span style="color:#5a6a7e;font-size:12px">🕐 Last sync:
                <b style="color:#a0aab4">{age_str}</b></span>
            <div style="background:{status_color}18;border:1px solid {status_color}55;
                        border-radius:20px;padding:5px 14px;
                        display:flex;align-items:center;gap:6px;">
                <div style="width:7px;height:7px;border-radius:50%;
                            background:{status_color};box-shadow:0 0 5px {status_color}"></div>
                <span style="color:{status_color};font-size:12px;font-weight:600">{status_label}</span>
            </div>
        </div>
    </div>
    """,
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
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
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

# ── Main content ───────────────────────────────────────────────────────
# Map height and right-panel height are kept identical so both columns end together.
MAP_H = 440

map_col, right_col = st.columns([3, 2])
LC = {"Clear": "#4caf50", "Moderate": "#ffb74d", "High": "#ef5350", "Critical": "#b71c1c"}

# ── Left: world map ────────────────────────────────────────────────────
with map_col:
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
            showland=True,      landcolor="#1a1f2e",
            showocean=True,     oceancolor="#0d1218",
            showlakes=False,
            showcountries=True, countrycolor="#263044",
            showframe=False,    bgcolor="#0f1117",
        ),
        paper_bgcolor="#0f1117",
        margin=dict(l=0, r=0, t=30, b=0),
        height=MAP_H,
        title=dict(text="Port Congestion Map", font=dict(color="#a0aab4", size=12), x=0),
        legend=dict(
            bgcolor="#1a1f2e", bordercolor="#263044",
            font=dict(color="#a0aab4", size=11),
            orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.0,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Right: ports + alerts in one fixed-height HTML block ───────────────
with right_col:
    # Build ports HTML (top 3)
    ports_html = ""
    for _, row in df_cong.head(3).iterrows():
        lc = LC.get(row.get("label", ""), "#a0aab4")
        ports_html += (
            f'<div style="display:flex;align-items:center;padding:11px 14px;margin-bottom:6px;'
            f'background:#1a1f2e;border-radius:8px;border:1px solid #263044;border-left:3px solid {lc};">'
            f'<div style="flex:1;min-width:0;">'
            f'  <div style="color:#e8eaed;font-size:14px;font-weight:600;'
            f'       white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'  <div style="color:#5a6a7e;font-size:12px;margin-top:2px">{row["country"]} · {row["vessel_count"]} vessels</div>'
            f'</div>'
            f'<div style="text-align:right;flex-shrink:0;margin-left:12px;">'
            f'  <span style="color:{lc};font-size:18px;font-weight:800">{row["score"]}</span>'
            f'  <span style="color:#5a6a7e;font-size:11px"> /100</span>'
            f'</div>'
            f'</div>'
        )

    # Build alerts + news HTML (max 3 total)
    cards_html = ""

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        sev   = "CRITICAL" if row["score"] >= 86 else "HIGH"
        color = "#b71c1c"  if sev == "CRITICAL"  else "#ef5350"
        cards_html += (
            f'<div style="background:{color}18;border:1px solid {color}44;'
            f'border-left:3px solid {color};border-radius:0 8px 8px 0;'
            f'padding:10px 14px;margin-bottom:6px;">'
            f'<div style="color:{color};font-size:10px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em">{sev}</div>'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:2px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'<div style="color:#6b7fa3;font-size:12px;margin-top:2px">'
            f'Congestion {row["score"]}/100 · {row["vessel_count"]} vessels nearby</div>'
            f'</div>'
        )

    if bdi.get("trend") == "rising":
        cards_html += (
            f'<div style="background:#ffb74d18;border:1px solid #ffb74d44;'
            f'border-left:3px solid #ffb74d;border-radius:0 8px 8px 0;'
            f'padding:10px 14px;margin-bottom:6px;">'
            f'<div style="color:#ffb74d;font-size:10px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em">WATCH</div>'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:2px">Rising BDI</div>'
            f'<div style="color:#6b7fa3;font-size:12px;margin-top:2px">'
            f'Index {bdi.get("value","N/A")} · {bdi_chg:+.1f}% today</div>'
            f'</div>'
        )

    for item in get_maritime_news(n=3):
        url_open  = f'<a href="{item["url"]}" target="_blank" style="text-decoration:none;display:block">' if item.get("url") else '<div>'
        url_close = '</a>' if item.get("url") else '</div>'
        cards_html += (
            f'<div style="background:#1a1f2e;border:1px solid #263044;'
            f'border-left:3px solid #00d4ff;border-radius:0 8px 8px 0;'
            f'padding:10px 14px;margin-bottom:6px;">'
            f'<div style="color:#00d4ff;font-size:10px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em">NEWS</div>'
            f'{url_open}'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:2px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{item["title"]}</div>'
            f'{url_close}'
            f'<div style="color:#5a6a7e;font-size:12px;margin-top:2px">{item["source"]}</div>'
            f'</div>'
        )

    if not cards_html:
        cards_html = (
            '<div style="background:#0a2010;border:1px solid #1a6640;'
            'border-left:3px solid #4caf50;border-radius:0 8px 8px 0;padding:10px 14px;">'
            '<div style="color:#4caf50;font-size:10px;font-weight:700;text-transform:uppercase">CLEAR</div>'
            '<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:2px">No Active Alerts</div>'
            '<div style="color:#6b7fa3;font-size:12px;margin-top:2px">All ports below threshold</div>'
            '</div>'
        )

    # Render entire right column as one block — no extra Streamlit element spacing
    st.markdown(
        f"""
        <div style="height:{MAP_H}px;display:flex;flex-direction:column;overflow:hidden;">

            <!-- Top half: congested ports -->
            <div style="display:flex;flex-direction:column;">
                <div style="color:#a0aab4;font-size:11px;font-weight:600;
                            text-transform:uppercase;letter-spacing:.07em;
                            margin-bottom:8px;">Top Congested Ports</div>
                {ports_html}
            </div>

            <!-- Divider -->
            <div style="border-top:1px solid #1e2736;margin:10px 0;flex-shrink:0;"></div>

            <!-- Bottom half: alerts + news -->
            <div style="display:flex;flex-direction:column;flex:1;overflow:hidden;">
                <div style="color:#a0aab4;font-size:11px;font-weight:600;
                            text-transform:uppercase;letter-spacing:.07em;
                            margin-bottom:8px;">Live Alerts &amp; News</div>
                {cards_html}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )
