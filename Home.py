import json
import os
from concurrent.futures import ThreadPoolExecutor
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
    with ThreadPoolExecutor(max_workers=3) as _ex:
        _v = _ex.submit(aisstream.get_vessels, bounding_boxes)
        _b = _ex.submit(get_bdi)
        _n = _ex.submit(get_maritime_news, 3)
        vessels    = _v.result()
        bdi        = _b.result()
        news_items = _n.result()
    congestion_data = cong_svc.get_all_port_congestion(vessels)

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
def _kpi(label, value, sub, sub_color="#6b7fa3", border_color=None, icon=""):
    bl = f"border-left:4px solid {border_color};" if border_color else ""
    ic = f'<span style="font-size:22px;opacity:0.6;line-height:1">{icon}</span>' if icon else ""
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;{bl}'
        f'border-radius:10px;padding:16px 20px;height:90px;'
        f'display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
        f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{label}</div>'
        f'{ic}</div>'
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{sub_color};font-size:12px">{sub}</div>'
        f'</div>'
    )

bdi_color   = "#ef5350" if bdi_chg > 0 else "#4caf50" if bdi_chg < 0 else "#6b7fa3"
crit_color  = "#ef5350" if critical_n > 0 else "#4caf50"
alert_color = "#ef5350" if alert_count > 3 else "#ffb74d" if alert_count > 0 else "#4caf50"

c1, c2, c3, c4 = st.columns(4)
c1.markdown(_kpi("Vessels Tracked",  f"{len(vessels):,}",       f"across {len(ports)} ports",       "#6b7fa3",   "#00d4ff", "🚢"), unsafe_allow_html=True)
c2.markdown(_kpi("Critical Ports",   str(critical_n),            f"{high_n} high risk",            crit_color,  "#ef5350" if critical_n > 0 else "#4caf50", "⚓"), unsafe_allow_html=True)
c3.markdown(_kpi("Active Alerts",    str(alert_count),           f"${alert_cost:.0f}M exposure",   alert_color, "#ef5350" if alert_count > 0 else "#4caf50", "⚠️"), unsafe_allow_html=True)
c4.markdown(_kpi("BDI",             str(bdi.get("value", "—")), f"{bdi_chg:+.1f}% · {bdi.get('trend','—').upper()}", bdi_color, bdi_color, "📈"), unsafe_allow_html=True)

# ── Main content ───────────────────────────────────────────────────────
MAP_H = 480

map_col, right_col = st.columns([2, 1])
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

# ── Right: two panel boxes ─────────────────────────────────────────────
with right_col:
    CARD_GAP = "12px"
    PANEL = (
        'background:#1a1f2e;border:1px solid #263044;border-radius:12px;'
        'padding:20px;display:flex;flex-direction:column;gap:' + CARD_GAP + ';'
        'box-shadow:0 2px 10px rgba(0,0,0,0.3);'
    )
    TITLE = 'color:#e8eaed;font-size:15px;font-weight:700;margin:0;'

    # ── Port rows ───────────────────────────────────────────────────────
    port_rows = []
    for _, row in df_cong.head(2).iterrows():
        lc = LC.get(row.get("label", ""), "#a0aab4")
        port_rows.append(
            '<div style="background:#0d1117;border:1px solid #263044;'
            'border-left:4px solid ' + lc + ';border-radius:8px;'
            'padding:12px 16px;display:flex;align-items:center;">'
            '<div style="flex:1;min-width:0;">'
            '<div style="color:#e8eaed;font-size:14px;font-weight:600;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
            + str(row["name"]) +
            '</div>'
            '<div style="color:#5a6a7e;font-size:12px;margin-top:3px">'
            + str(row["country"]) + ' · ' + str(row["vessel_count"]) + ' vessels'
            '</div>'
            '</div>'
            '<div style="flex-shrink:0;margin-left:12px;">'
            '<span style="color:' + lc + ';font-size:22px;font-weight:800">'
            + str(row["score"]) +
            '</span>'
            '<span style="color:#5a6a7e;font-size:11px"> /100</span>'
            '</div>'
            '</div>'
        )
    if not port_rows:
        port_rows.append(
            '<div style="background:#0d1117;border:1px solid #263044;border-radius:8px;'
            'padding:12px 16px;color:#5a6a7e;font-size:13px">No congestion data yet</div>'
        )

    # ── Alert / news cards ───────────────────────────────────────────────
    alert_cards = []

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        if len(alert_cards) >= 3:
            break
        if row["score"] >= 86:
            bg, bdr = "#ef535018", "#ef5350"
            title_c, desc_c, time_c = "#ef5350", "#ef9a9a", "#e57373"
            title = "Critical Congestion Detected"
        else:
            bg, bdr = "#ffa72618", "#ffa726"
            title_c, desc_c, time_c = "#ffa726", "#ffcc80", "#ffb74d"
            title = "High Congestion Alert"
        desc = str(row["name"]) + " · " + str(row["score"]) + "/100 · " + str(row["vessel_count"]) + " vessels"
        alert_cards.append(
            '<div style="background:' + bg + ';border-left:4px solid ' + bdr + ';'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:' + title_c + ';font-size:14px;font-weight:700">' + title + '</div>'
            '<div style="color:' + desc_c + ';font-size:13px;margin-top:4px">' + desc + '</div>'
            '<div style="color:' + time_c + ';font-size:11px;margin-top:4px">Just now</div>'
            '</div>'
        )

    if bdi.get("trend") == "rising" and len(alert_cards) < 3:
        bdi_desc = "BDI index " + str(bdi.get("value", "N/A")) + " · " + f"{bdi_chg:+.1f}%" + " today"
        alert_cards.append(
            '<div style="background:#ffa72618;border-left:4px solid #ffa726;'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:#ffa726;font-size:14px;font-weight:700">Freight Rate Rising</div>'
            '<div style="color:#ffcc80;font-size:13px;margin-top:4px">' + bdi_desc + '</div>'
            '<div style="color:#ffb74d;font-size:11px;margin-top:4px">Just now</div>'
            '</div>'
        )

    for item in news_items[:3 - len(alert_cards)]:
        url_a = 'href="' + item["url"] + '" target="_blank"' if item.get("url") else ""
        alert_cards.append(
            '<div style="background:#00d4ff18;border-left:4px solid #00d4ff;'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:#00d4ff;font-size:14px;font-weight:700">'
            '<a ' + url_a + ' style="color:#00d4ff;text-decoration:none;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block">'
            + str(item["title"]) + '</a></div>'
            '<div style="color:#80deea;font-size:13px;margin-top:4px">' + str(item["source"]) + '</div>'
            '<div style="color:#5a6a7e;font-size:11px;margin-top:4px">Maritime News</div>'
            '</div>'
        )

    if not alert_cards:
        alert_cards.append(
            '<div style="background:#4caf5018;border-left:4px solid #4caf50;'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:#4caf50;font-size:14px;font-weight:700">All Systems Clear</div>'
            '<div style="color:#a5d6a7;font-size:13px;margin-top:4px">No active congestion alerts</div>'
            '<div style="color:#81c784;font-size:11px;margin-top:4px">All ports below threshold</div>'
            '</div>'
        )

    right_html = (
        '<div style="' + PANEL + 'margin-bottom:25px;">'
        '<div style="' + TITLE + '">📍 Top Congested Ports</div>'
        + "".join(port_rows) +
        '</div>'
        '<div style="' + PANEL + '">'
        '<div style="' + TITLE + '">🔔 Live Alerts &amp; News</div>'
        + "".join(alert_cards) +
        '</div>'
    )
    st.markdown(right_html, unsafe_allow_html=True)
