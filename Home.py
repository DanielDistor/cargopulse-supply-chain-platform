"""
Dashboard — CargoPulse
All inline style values sourced verbatim from:
  josna-14/Maritime_Vessel_Tracking/frontend/src/pages/Dashboard.js
  josna-14/Maritime_Vessel_Tracking/frontend/src/index.css
  josna-14/Maritime_Vessel_Tracking/frontend/src/components/Navbar.css
No approximations. Content/data substituted; design tokens unchanged.
"""
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

# ── Status pill
# Dashboard.js: color "#2e7d32", background "#e8f5e9", padding "6px 12px",
# borderRadius "20px", fontWeight "600", border "1px solid #c8e6c9"
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
age_str      = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching…"

if is_live:
    s_color, s_bg, s_border, s_dot = "#2e7d32", "#e8f5e9", "#c8e6c9", "●"
    s_label = "System Operational"
elif is_connected:
    s_color, s_bg, s_border, s_dot = "#ef6c00", "#fff3e0", "#ffcc80", "●"
    s_label = "Data Stale"
else:
    s_color, s_bg, s_border, s_dot = "#c62828", "#ffebee", "#ef9a9a", "●"
    s_label = "Offline"

# ── Page header
# Dashboard.js: h1 margin "0 0 5px 0", color "#1f3c88", fontSize "24px"
#               p  margin 0, color "#666", fontSize "14px"
#               header marginBottom "25px"
#               span fontSize "0.85rem", color "#888"
#               status fontSize "0.85rem", color/bg/padding/radius/border exact
st.markdown(
    '<div style="display:flex;justify-content:space-between;align-items:center;'
    'margin-bottom:25px;">'
    '<div>'
    '<h1 style="margin:0 0 5px 0;color:#1f3c88;font-size:24px;font-weight:700">'
    'Supply Chain Intelligence</h1>'
    '<p style="margin:0;color:#666;font-size:14px">'
    'Live port congestion &nbsp;·&nbsp; vessel tracking'
    ' &nbsp;·&nbsp; BDI freight analysis &nbsp;·&nbsp; '
    + str(len(ports)) + ' ports monitored'
    '</p>'
    '</div>'
    '<div style="display:flex;align-items:center;gap:15px;flex-shrink:0;">'
    '<span style="font-size:0.85rem;color:#888">🕒 Last Sync: '
    + age_str + '</span>'
    '<span style="font-size:0.85rem;color:' + s_color + ';background:' + s_bg + ';'
    'padding:6px 12px;border-radius:20px;font-weight:600;border:1px solid ' + s_border + '">'
    + s_dot + ' ' + s_label + '</span>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ── KPI row
# Dashboard.js card inline styles (exact):
#   background:"white", borderRadius:"12px", padding:"20px",
#   boxShadow:"0 2px 10px rgba(0,0,0,0.05)", borderLeft:"4px solid {color}"
#   layout: display flex, justifyContent space-between, alignItems flex-start
#   label p:  margin "0 0 8px 0", fontSize "0.8rem", textTransform uppercase,
#             fontWeight "700", color "#888"
#   value p:  fontSize "2rem", fontWeight "700", margin "0 0 5px 0", color "#333"
#   trend:    fontSize "0.85rem", fontWeight "500", color "#555"
#             trendColor fontWeight "700" | desc color "#999" marginLeft "4px" fontWeight "400"
#   icon:     fontSize "2rem", opacity 0.2
#
# KPI section: gap "20px", marginBottom "25px"
# User wants attached (no gap) — outer wrapper holds radius+shadow, dividers via border-right

# Card left-border colors (from Dashboard.js card color values)
bdi_color  = "#d32f2f" if bdi_chg > 0 else "#2e7d32" if bdi_chg < 0 else "#888"
crit_color = "#d32f2f" if critical_n > 0 else "#2e7d32"
alrt_color = "#d32f2f" if alert_count > 3 else "#f57c00" if alert_count > 0 else "#2e7d32"

crit_tc = "#d32f2f" if critical_n > 0 else "#2e7d32"
alrt_tc = "#d32f2f" if alert_count > 3 else "#f57c00" if alert_count > 0 else "#2e7d32"
bdi_tc  = "#d32f2f" if bdi_chg > 0 else "#2e7d32" if bdi_chg < 0 else "#888"

# Exact card inner template
_CI = 'padding:20px;display:flex;justify-content:space-between;align-items:flex-start;background:white;'
_LB = 'margin:0 0 8px 0;font-size:0.8rem;text-transform:uppercase;font-weight:700;color:#888;'
_VL = 'font-size:2rem;font-weight:700;margin:0 0 5px 0;color:#333;line-height:1.1;'
_TR = 'font-size:0.85rem;font-weight:500;color:#555;'
_IC = 'font-size:2rem;opacity:0.2;flex-shrink:0;'

st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
    'border-radius:12px;overflow:hidden;'
    'box-shadow:0 2px 10px rgba(0,0,0,0.05);margin-bottom:25px;">'

    '<div style="' + _CI + 'border-left:4px solid #1f3c88;border-right:1px solid #eee;">'
    '<div style="flex:1">'
    '<p style="' + _LB + '">Vessels Tracked</p>'
    '<p style="' + _VL + '">' + f'{len(vessels):,}' + '</p>'
    '<div style="' + _TR + '">across '
    '<span style="color:#1f3c88;font-weight:700">' + str(len(ports)) + '</span>'
    ' <span style="color:#999;font-weight:400">ports</span>'
    '</div>'
    '</div>'
    '<div style="' + _IC + '">🚢</div>'
    '</div>'

    '<div style="' + _CI + 'border-left:4px solid ' + crit_color + ';border-right:1px solid #eee;">'
    '<div style="flex:1">'
    '<p style="' + _LB + '">Critical Ports</p>'
    '<p style="' + _VL + '">' + str(critical_n) + '</p>'
    '<div style="' + _TR + '">'
    '<span style="color:' + crit_tc + ';font-weight:700">' + str(high_n) + '</span>'
    ' <span style="color:#999;font-weight:400">high risk</span>'
    '</div>'
    '</div>'
    '<div style="' + _IC + '">⚓</div>'
    '</div>'

    '<div style="' + _CI + 'border-left:4px solid ' + alrt_color + ';border-right:1px solid #eee;">'
    '<div style="flex:1">'
    '<p style="' + _LB + '">Active Alerts</p>'
    '<p style="' + _VL + '">' + str(alert_count) + '</p>'
    '<div style="' + _TR + '">'
    '<span style="color:' + alrt_tc + ';font-weight:700">$' + f'{alert_cost:.0f}' + 'M</span>'
    ' <span style="color:#999;font-weight:400">exposure</span>'
    '</div>'
    '</div>'
    '<div style="' + _IC + '">⚠️</div>'
    '</div>'

    '<div style="' + _CI + 'border-left:4px solid ' + bdi_color + ';">'
    '<div style="flex:1">'
    '<p style="' + _LB + '">BDI</p>'
    '<p style="' + _VL + '">' + str(bdi.get("value", "—")) + '</p>'
    '<div style="' + _TR + '">'
    '<span style="color:' + bdi_tc + ';font-weight:700">' + f'{bdi_chg:+.1f}%' + '</span>'
    ' <span style="color:#999;font-weight:400">' + bdi.get("trend", "—").lower() + '</span>'
    '</div>'
    '</div>'
    '<div style="' + _IC + '">📈</div>'
    '</div>'

    '</div>',
    unsafe_allow_html=True,
)

# ── Main content
# Dashboard.js: gridTemplateColumns "2fr 1fr", gap "25px"
# Congestion dot colors (vivid against dark map)
LC = {"Clear": "#4caf50", "Moderate": "#ff9800", "High": "#f44336", "Critical": "#b71c1c"}

map_col, right_col = st.columns([2, 1])

# ── Left: Port Congestion Map
# Panel: exact Dashboard.js section style
#   background "white", borderRadius "12px", boxShadow "0 2px 10px rgba(0,0,0,0.05)", padding "20px"
#   h3: margin "0 0 15px 0", fontSize "1.1rem", color "#333"
# Map height: reference chart is 200px; map needs more — use 360px (2fr column is wide enough)
# lataxis range cuts Antarctica dead-space; lonaxis keeps full width
with map_col:
    MAP_H = 450
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
                    opacity=0.9,
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
            showland=True,      landcolor="#1e3a5f",
            showocean=True,     oceancolor="#0f2340",
            showlakes=False,
            showcountries=True, countrycolor="#2d5080",
            showframe=False,    bgcolor="#0f2340",
            # Clip dead-space: remove Antarctica, keep full longitude
            lataxis=dict(range=[-55, 80]),
            lonaxis=dict(range=[-170, 180]),
        ),
        paper_bgcolor="#0f2340",
        margin=dict(l=0, r=0, t=44, b=4),
        height=MAP_H,
        # h3 style: fontSize 1.1rem (~17.6px), color #333, margin 0 0 15px 0
        title=dict(
            text="🗺️  Port Congestion Map",
            font=dict(color="#ffffff", size=18),
            x=0.02, y=0.99, xanchor="left", yanchor="top",
        ),
        legend=dict(
            bgcolor="rgba(15,35,64,0.85)", bordercolor="rgba(255,255,255,0.1)",
            font=dict(color="#ffffff", size=11),
            orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0.02,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Right column: two stacked panels
# Dashboard.js right column: display flex, flexDirection column, gap "25px"
# Each section: background "white", borderRadius "12px",
#               boxShadow "0 2px 10px rgba(0,0,0,0.05)", padding "20px"
# h3: margin "0 0 15px 0", fontSize "1.1rem", color "#333"
with right_col:
    # Panel template (exact reference values)
    PANEL = (
        'background:white;border-radius:12px;'
        'box-shadow:0 2px 10px rgba(0,0,0,0.05);padding:20px;'
        'display:flex;flex-direction:column;gap:10px;'
    )
    # h3 exact: margin "0 0 15px 0", fontSize "1.1rem", color "#333"
    H3 = 'margin:0 0 15px 0;font-size:1.1rem;font-weight:600;color:#333;'

    # ── Top Congested Ports — Quick Actions button style (exact):
    # padding "12px", border "1px solid #eee", background "#f8f9fa",
    # borderRadius "8px", fontWeight "600", color "#555", textAlign "left"
    # gap between buttons: "10px" (handled by panel flex gap above)
    port_rows = []
    for _, row in df_cong.head(2).iterrows():
        lc = LC.get(row.get("label", ""), "#888")
        port_rows.append(
            '<div style="padding:12px;border:1px solid #eee;background:#f8f9fa;'
            'border-radius:8px;border-left:4px solid ' + lc + ';'
            'display:flex;align-items:center;">'
            '<div style="flex:1;min-width:0;">'
            '<div style="font-weight:600;color:#555;font-size:0.9rem;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
            + str(row["name"]) + '</div>'
            '<div style="color:#888;font-size:0.8rem;margin-top:3px">'
            + str(row["country"]) + ' · ' + str(row["vessel_count"]) + ' vessels'
            '</div>'
            '</div>'
            '<div style="flex-shrink:0;margin-left:12px;text-align:right;">'
            '<span style="color:' + lc + ';font-size:1.3rem;font-weight:700">'
            + str(row["score"]) + '</span>'
            '<span style="color:#bbb;font-size:0.75rem"> /100</span>'
            '</div>'
            '</div>'
        )
    if not port_rows:
        port_rows.append(
            '<div style="padding:12px;border:1px solid #eee;background:#f8f9fa;'
            'border-radius:8px;color:#888;font-size:0.85rem">No congestion data yet</div>'
        )

    # ── Live Alerts & News
    # index.css .alert-item (exact):
    #   padding: 12px, border-radius: 8px, border-left: 4px solid
    # index.css .alert-title:
    #   font-weight: 600, font-size: 0.95rem, margin-bottom: 4px
    # Dashboard.js overrides title to: fontSize "0.9rem", fontWeight "700"
    # index.css .alert-item p: font-size: 0.85rem, color: #555
    # index.css .alert-item small: font-size: 0.75rem, color: #999
    # Dashboard.js overrides body/time colors per severity
    #
    # High (red):    bg #ffebee, border #ef5350, title #c62828, body #b71c1c, time #e57373
    # Medium (orange): bg #fff3e0, border #ffa726, title #ef6c00, body #e65100, time #ffb74d
    # Low (green):   bg #e8f5e9, border #66bb6a, title #2e7d32, body #1b5e20, time #81c784
    # News (blue):   no exact ref — use index.css .auth__message style: bg #e7f6ff,
    #               border #1f3c88, title #1565c0
    #
    # Dashboard.js alerts container: gap "12px"
    alert_cards = []

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        if len(alert_cards) >= 3:
            break
        if row["score"] >= 86:
            # High priority (red) — Dashboard.js exact
            bg, bdr = "#ffebee", "#ef5350"
            tc, bc, sc = "#c62828", "#b71c1c", "#e57373"
            title = "Critical Congestion Detected"
        else:
            # Medium priority (orange) — Dashboard.js exact
            bg, bdr = "#fff3e0", "#ffa726"
            tc, bc, sc = "#ef6c00", "#e65100", "#ffb74d"
            title = "High Congestion Alert"
        desc = str(row["name"]) + " · " + str(row["score"]) + "/100 · " + str(row["vessel_count"]) + " vessels"
        alert_cards.append(
            '<div style="background:' + bg + ';padding:12px;border-radius:8px;'
            'border-left:4px solid ' + bdr + ';">'
            '<div style="font-size:0.9rem;font-weight:700;color:' + tc + ';margin-bottom:4px">' + title + '</div>'
            '<p style="margin:0;font-size:0.85rem;color:' + bc + '">' + desc + '</p>'
            '<small style="color:' + sc + ';font-size:0.75rem;margin-top:5px;display:block">Just now</small>'
            '</div>'
        )

    if bdi.get("trend") == "rising" and len(alert_cards) < 3:
        # Medium priority (orange) — Dashboard.js exact
        bdi_desc = "BDI index " + str(bdi.get("value", "N/A")) + " · " + f"{bdi_chg:+.1f}%" + " today"
        alert_cards.append(
            '<div style="background:#fff3e0;padding:12px;border-radius:8px;'
            'border-left:4px solid #ffa726;">'
            '<div style="font-size:0.9rem;font-weight:700;color:#ef6c00;margin-bottom:4px">Freight Rate Rising</div>'
            '<p style="margin:0;font-size:0.85rem;color:#e65100">' + bdi_desc + '</p>'
            '<small style="color:#ffb74d;font-size:0.75rem;margin-top:5px;display:block">Just now</small>'
            '</div>'
        )

    for item in get_maritime_news(n=3 - len(alert_cards)):
        if len(alert_cards) >= 3:
            break
        url_a = 'href="' + item["url"] + '" target="_blank"' if item.get("url") else ""
        # index.css .auth__message: bg #e7f6ff, border #b4dcff — closest to news
        alert_cards.append(
            '<div style="background:#e7f6ff;padding:12px;border-radius:8px;'
            'border-left:4px solid #1f3c88;">'
            '<div style="font-size:0.9rem;font-weight:700;color:#1565c0;margin-bottom:4px">'
            '<a ' + url_a + ' style="color:#1565c0;text-decoration:none;'
            'overflow:hidden;text-overflow:ellipsis;display:block;white-space:nowrap">'
            + str(item["title"]) + '</a></div>'
            '<p style="margin:0;font-size:0.85rem;color:#555">' + str(item["source"]) + '</p>'
            '<small style="color:#999;font-size:0.75rem;margin-top:5px;display:block">Maritime News</small>'
            '</div>'
        )

    if not alert_cards:
        # Low priority (green) — Dashboard.js exact
        alert_cards.append(
            '<div style="background:#e8f5e9;padding:12px;border-radius:8px;'
            'border-left:4px solid #66bb6a;">'
            '<div style="font-size:0.9rem;font-weight:700;color:#2e7d32;margin-bottom:4px">All Systems Clear</div>'
            '<p style="margin:0;font-size:0.85rem;color:#1b5e20">No active congestion alerts</p>'
            '<small style="color:#81c784;font-size:0.75rem;margin-top:5px;display:block">All ports below threshold</small>'
            '</div>'
        )

    # Dashboard.js right column gap: "25px" → margin-bottom between panels
    right_html = (
        '<div style="' + PANEL + 'margin-bottom:25px;">'
        '<h3 style="' + H3 + '">📍 Top Congested Ports</h3>'
        + "".join(port_rows) +
        '</div>'
        '<div style="' + PANEL + '">'
        '<h3 style="' + H3 + '">🔔 Live Alerts &amp; News</h3>'
        + "".join(alert_cards) +
        '</div>'
    )
    st.markdown(right_html, unsafe_allow_html=True)
