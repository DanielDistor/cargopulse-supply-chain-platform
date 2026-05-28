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
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;{bl}'
        f'border-radius:10px;padding:16px 20px;height:88px;'
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
c1.markdown(_kpi("Vessels Tracked",  f"{len(vessels):,}",       f"across {len(ports)} ports",       "#6b7fa3",   "#00d4ff"),              unsafe_allow_html=True)
c2.markdown(_kpi("Critical Ports",   str(critical_n),            f"{high_n} high risk",            crit_color,  "#ef5350" if critical_n > 0 else "#4caf50"), unsafe_allow_html=True)
c3.markdown(_kpi("Active Alerts",    str(alert_count),           f"${alert_cost:.0f}M exposure",   alert_color, "#ef5350" if alert_count > 0 else "#4caf50"), unsafe_allow_html=True)
c4.markdown(_kpi("BDI",             str(bdi.get("value", "—")), f"{bdi_chg:+.1f}% · {bdi.get('trend','—').upper()}", bdi_color, bdi_color),            unsafe_allow_html=True)

# Spacer so KPI row doesn't visually bleed into the panels below
st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

# ── Main content ───────────────────────────────────────────────────────
MAP_H = 520

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

# ── Right: two panel boxes — flex gap controls ALL spacing uniformly ───
with right_col:
    # One gap value used everywhere: between title→card and card→card.
    # No individual margin-bottom anywhere — that was the unevenness.
    GAP = "10px"
    PANEL = (
        f'background:#1a1f2e;border:1px solid #263044;border-radius:14px;'
        f'padding:16px;display:flex;flex-direction:column;gap:{GAP};'
    )
    TITLE = 'color:#e8eaed;font-size:15px;font-weight:700;'

    # ── Port rows ───────────────────────────────────────────────────────
    port_html = ""
    for _, row in df_cong.head(2).iterrows():
        lc = LC.get(row.get("label", ""), "#a0aab4")
        port_html += (
            f'<div style="background:#0d1117;border-radius:10px;padding:14px 16px;'
            f'display:flex;align-items:center;border-left:3px solid {lc};">'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'<div style="color:#5a6a7e;font-size:12px;margin-top:4px">'
            f'{row["country"]} · {row["vessel_count"]} vessels</div>'
            f'</div>'
            f'<div style="flex-shrink:0;margin-left:12px;">'
            f'<span style="color:{lc};font-size:22px;font-weight:800">{row["score"]}</span>'
            f'<span style="color:#5a6a7e;font-size:11px"> /100</span>'
            f'</div>'
            f'</div>'
        )
    if not port_html:
        port_html = (
            '<div style="background:#0d1117;border-radius:10px;padding:14px 16px;'
            'color:#5a6a7e;font-size:13px">No congestion data yet</div>'
        )

    # ── Alert / news cards ──────────────────────────────────────────────
    alert_html = ""
    n_cards = 0

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        if n_cards >= 3:
            break
        sev   = "CRITICAL" if row["score"] >= 86 else "HIGH"
        col   = "#c62828"  if sev == "CRITICAL"  else "#ef5350"
        alert_html += (
            f'<div style="background:{col}1a;border-radius:10px;padding:12px 16px;'
            f'border-left:3px solid {col};">'
            f'<div style="color:{col};font-size:10px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em">{sev}</div>'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:3px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'<div style="color:#8899a6;font-size:12px;margin-top:2px">'
            f'Congestion {row["score"]}/100 · {row["vessel_count"]} vessels nearby</div>'
            f'</div>'
        )
        n_cards += 1

    if bdi.get("trend") == "rising" and n_cards < 3:
        alert_html += (
            '<div style="background:#ffb74d1a;border-radius:10px;padding:12px 16px;'
            'border-left:3px solid #ffb74d;">'
            '<div style="color:#ffb74d;font-size:10px;font-weight:700;'
            'text-transform:uppercase;letter-spacing:.06em">WATCH</div>'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:3px">Rising BDI</div>'
            f'<div style="color:#8899a6;font-size:12px;margin-top:2px">'
            f'Index {bdi.get("value","N/A")} · {bdi_chg:+.1f}% today</div>'
            '</div>'
        )
        n_cards += 1

    for item in get_maritime_news(n=3 - n_cards):
        if n_cards >= 3:
            break
        url_a = f'href="{item["url"]}" target="_blank"' if item.get("url") else ""
        alert_html += (
            '<div style="background:#131a24;border-radius:10px;padding:12px 16px;'
            'border-left:3px solid #00d4ff;">'
            '<div style="color:#00d4ff;font-size:10px;font-weight:700;'
            'text-transform:uppercase;letter-spacing:.06em">NEWS</div>'
            f'<a {url_a} style="text-decoration:none;">'
            f'<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:3px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{item["title"]}</div>'
            '</a>'
            f'<div style="color:#5a6a7e;font-size:12px;margin-top:2px">{item["source"]}</div>'
            '</div>'
        )
        n_cards += 1

    if not alert_html:
        alert_html = (
            '<div style="background:#0a20101a;border-radius:10px;padding:12px 16px;'
            'border-left:3px solid #4caf50;">'
            '<div style="color:#4caf50;font-size:10px;font-weight:700;text-transform:uppercase">CLEAR</div>'
            '<div style="color:#e8eaed;font-size:14px;font-weight:600;margin-top:3px">No Active Alerts</div>'
            '<div style="color:#8899a6;font-size:12px;margin-top:2px">All ports below threshold</div>'
            '</div>'
        )

    # Panels: flex column with gap={GAP} handles title→card and card→card spacing.
    # The SAME gap value everywhere = perfectly uniform margins throughout.
    right_html = (
        f'<div style="{PANEL}margin-bottom:{GAP};">'
        f'<div style="{TITLE}">📍 Top Congested Ports</div>'
        + port_html +
        f'</div>'
        f'<div style="{PANEL}">'
        f'<div style="{TITLE}">🔔 Live Alerts &amp; News</div>'
        + alert_html +
        f'</div>'
    )
    st.markdown(right_html, unsafe_allow_html=True)
