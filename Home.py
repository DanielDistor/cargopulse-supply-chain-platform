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

# ── Status pill — exact reference styles ───────────────────────────────
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
age_str      = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching…"

if is_live:
    # reference: color #2e7d32, bg #e8f5e9, border #c8e6c9
    s_color, s_bg, s_border, s_label = "#2e7d32", "#e8f5e9", "#c8e6c9", "System Operational"
elif is_connected:
    s_color, s_bg, s_border, s_label = "#ef6c00", "#fff3e0", "#ffcc80", "Data Stale"
else:
    s_color, s_bg, s_border, s_label = "#c62828", "#ffebee", "#ef9a9a", "Offline"

# ── Page header — reference: h1 color #1f3c88 24px, subtitle #666 14px ─
st.markdown(
    '<div style="display:flex;justify-content:space-between;align-items:center;'
    'margin-bottom:14px;">'
    '<div>'
    '<h1 style="margin:0 0 4px 0;color:#1f3c88;font-size:20px;font-weight:700">'
    'Supply Chain Intelligence</h1>'
    '<p style="margin:0;color:#777;font-size:13px">'
    'Live port congestion &nbsp;·&nbsp; vessel tracking'
    ' &nbsp;·&nbsp; BDI freight analysis &nbsp;·&nbsp; '
    + str(len(ports)) + ' ports monitored'
    '</p>'
    '</div>'
    '<div style="display:flex;align-items:center;gap:15px;flex-shrink:0;">'
    '<span style="font-size:0.8rem;color:#999">🕒 Last Sync: '
    '<b style="color:#555">' + age_str + '</b></span>'
    '<span style="font-size:0.85rem;color:' + s_color + ';background:' + s_bg + ';'
    'padding:6px 12px;border-radius:20px;font-weight:600;border:1px solid ' + s_border + '">'
    '● ' + s_label + '</span>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ── KPI row — reference card style, user wants ATTACHED (no gaps) ──────
# Reference card: background white, borderRadius 12px, padding 20px,
# boxShadow 0 2px 10px rgba(0,0,0,0.05), borderLeft 4px solid {color}
# Label: 0.8rem uppercase fontWeight 700 color #888
# Value: 2rem fontWeight 700 color #333
# Sub: 0.85rem color #555 / trendColor
# Icon: 2rem opacity 0.2
# Attached: outer wrapper holds border-radius + shadow, inner dividers via border-right

# KPI border colors (from reference card colors)
bdi_color  = "#d32f2f" if bdi_chg > 0 else "#2e7d32" if bdi_chg < 0 else "#888"
crit_color = "#d32f2f" if critical_n > 0 else "#2e7d32"
alrt_color = "#d32f2f" if alert_count > 3 else "#f57c00" if alert_count > 0 else "#2e7d32"

crit_trend_c = "#d32f2f" if critical_n > 0 else "#2e7d32"
alrt_trend_c = "#d32f2f" if alert_count > 3 else "#f57c00" if alert_count > 0 else "#2e7d32"
bdi_trend_c  = "#d32f2f" if bdi_chg > 0 else "#2e7d32" if bdi_chg < 0 else "#888"

CARD_INNER = (
    'padding:14px 18px;display:flex;justify-content:space-between;'
    'align-items:flex-start;background:white;'
)
LABEL_S = 'margin:0 0 5px 0;font-size:0.72rem;text-transform:uppercase;font-weight:600;color:#999;letter-spacing:0.04em;'
VALUE_S = 'font-size:1.65rem;font-weight:700;margin:0 0 3px 0;color:#333;line-height:1;'
ICON_S  = 'font-size:1.5rem;opacity:0.18;'

st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
    'border-radius:8px;overflow:hidden;'
    'box-shadow:0 1px 4px rgba(0,0,0,0.06);margin-bottom:14px;">'

    # Card 1 — Vessels Tracked (reference blue #1f3c88)
    '<div style="' + CARD_INNER + 'border-left:4px solid #1f3c88;border-right:1px solid #f2f2f2;">'
    '<div>'
    '<p style="' + LABEL_S + '">Vessels Tracked</p>'
    '<p style="' + VALUE_S + '">' + f'{len(vessels):,}' + '</p>'
    '<div style="font-size:0.78rem;font-weight:400;color:#666">'
    'across <span style="color:#1f3c88;font-weight:700">' + str(len(ports)) + '</span>'
    ' <span style="color:#999;font-weight:400">ports</span>'
    '</div>'
    '</div>'
    '<div style="' + ICON_S + '">🚢</div>'
    '</div>'

    # Card 2 — Critical Ports (reference red #d32f2f)
    '<div style="' + CARD_INNER + 'border-left:4px solid ' + crit_color + ';border-right:1px solid #f2f2f2;">'
    '<div>'
    '<p style="' + LABEL_S + '">Critical Ports</p>'
    '<p style="' + VALUE_S + '">' + str(critical_n) + '</p>'
    '<div style="font-size:0.78rem;font-weight:400;color:#666">'
    '<span style="color:' + crit_trend_c + ';font-weight:700">' + str(high_n) + '</span>'
    ' <span style="color:#999;font-weight:400">high risk</span>'
    '</div>'
    '</div>'
    '<div style="' + ICON_S + '">⚓</div>'
    '</div>'

    # Card 3 — Active Alerts (reference orange #f57c00)
    '<div style="' + CARD_INNER + 'border-left:4px solid ' + alrt_color + ';border-right:1px solid #f2f2f2;">'
    '<div>'
    '<p style="' + LABEL_S + '">Active Alerts</p>'
    '<p style="' + VALUE_S + '">' + str(alert_count) + '</p>'
    '<div style="font-size:0.78rem;font-weight:400;color:#666">'
    '<span style="color:' + alrt_trend_c + ';font-weight:700">$' + f'{alert_cost:.0f}' + 'M</span>'
    ' <span style="color:#999;font-weight:400">exposure</span>'
    '</div>'
    '</div>'
    '<div style="' + ICON_S + '">⚠️</div>'
    '</div>'

    # Card 4 — BDI
    '<div style="' + CARD_INNER + 'border-left:4px solid ' + bdi_color + ';">'
    '<div>'
    '<p style="' + LABEL_S + '">BDI</p>'
    '<p style="' + VALUE_S + '">' + str(bdi.get("value", "—")) + '</p>'
    '<div style="font-size:0.78rem;font-weight:400;color:#666">'
    '<span style="color:' + bdi_trend_c + ';font-weight:700">' + f'{bdi_chg:+.1f}%' + '</span>'
    ' <span style="color:#999;font-weight:400">' + bdi.get("trend", "—").lower() + '</span>'
    '</div>'
    '</div>'
    '<div style="' + ICON_S + '">📈</div>'
    '</div>'

    '</div>',
    unsafe_allow_html=True,
)

# ── Main content grid — reference: gridTemplateColumns "2fr 1fr", gap 25px
# Congestion dot colors — vivid, readable on dark map
LC = {"Clear": "#4caf50", "Moderate": "#ff9800", "High": "#f44336", "Critical": "#b71c1c"}

map_col, right_col = st.columns([2, 1])

# ── Left: Port Congestion Map ──────────────────────────────────────────
# Panel: white bg, borderRadius 12px, boxShadow 0 2px 10px rgba(0,0,0,0.05), padding 20px
# Title h3: margin 0 0 15px 0, fontSize 1.1rem, color #333
with map_col:
    MAP_H = 395
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
        ),
        paper_bgcolor="#ffffff",
        margin=dict(l=10, r=10, t=44, b=8),
        height=MAP_H,
        title=dict(
            text="🗺️  Port Congestion Map",
            font=dict(color="#444", size=15),
            x=0.01, y=0.99, xanchor="left", yanchor="top",
        ),
        legend=dict(
            bgcolor="rgba(15,35,64,0.85)", bordercolor="rgba(255,255,255,0.1)",
            font=dict(color="#ffffff", size=11),
            orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0.02,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Right: two stacked panels ─────────────────────────────────────────
# Panel style — exact reference: white, borderRadius 12px,
# boxShadow 0 2px 10px rgba(0,0,0,0.05), padding 20px
# Gap between panels: 25px (reference right-column gap)
# Title h3: margin 0 0 15px 0, fontSize 1.1rem (17.6px), color #333
with right_col:
    PANEL = (
        'background:white;border-radius:8px;'
        'box-shadow:0 1px 4px rgba(0,0,0,0.06);padding:14px 16px;'
        'display:flex;flex-direction:column;gap:8px;'
    )
    H3 = 'margin:0 0 6px 0;font-size:0.95rem;font-weight:600;color:#444;'

    # ── Top Congested Ports — Quick Actions button style from reference ──
    # Button: padding 12px, border 1px solid #eee, background #f8f9fa,
    # borderRadius 8px, fontWeight 600, color #555
    port_rows = []
    for _, row in df_cong.head(2).iterrows():
        lc = LC.get(row.get("label", ""), "#888")
        port_rows.append(
            '<div style="padding:9px 12px;border:1px solid #f0f0f0;background:#fafafa;'
            'border-radius:6px;display:flex;align-items:center;'
            'border-left:3px solid ' + lc + ';">'
            '<div style="flex:1;min-width:0;">'
            '<div style="font-weight:600;color:#333;font-size:0.85rem;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
            + str(row["name"]) + '</div>'
            '<div style="color:#999;font-size:0.75rem;margin-top:2px">'
            + str(row["country"]) + ' · ' + str(row["vessel_count"]) + ' vessels'
            '</div>'
            '</div>'
            '<div style="flex-shrink:0;margin-left:10px;text-align:right;">'
            '<span style="color:' + lc + ';font-size:1.25rem;font-weight:700">'
            + str(row["score"]) + '</span>'
            '<span style="color:#bbb;font-size:0.7rem"> /100</span>'
            '</div>'
            '</div>'
        )
    if not port_rows:
        port_rows.append(
            '<div style="padding:9px 12px;border:1px solid #f0f0f0;background:#fafafa;'
            'border-radius:6px;color:#bbb;font-size:0.8rem">No congestion data yet</div>'
        )

    # ── Live Alerts & News — exact reference alert card colors ───────────
    # Red:    bg #ffebee, border #ef5350, title #c62828 0.9rem 700,
    #         body #b71c1c 0.85rem, time #e57373 0.75rem
    # Orange: bg #fff3e0, border #ffa726, title #ef6c00,
    #         body #e65100, time #ffb74d
    # Green:  bg #e8f5e9, border #66bb6a, title #2e7d32,
    #         body #1b5e20, time #81c784
    # Blue (news): bg #e3f2fd, border #1f3c88, title #1565c0,
    #         body #0d47a1, time #64b5f6
    alert_cards = []

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        if len(alert_cards) >= 3:
            break
        if row["score"] >= 86:
            bg, bdr, tc, bc, sc = "#fff5f5", "#e57373", "#c62828", "#888", "#bbb"
            title = "Critical Congestion Detected"
        else:
            bg, bdr, tc, bc, sc = "#fff9f0", "#ffb74d", "#d97706", "#888", "#bbb"
            title = "High Congestion Alert"
        desc = str(row["name"]) + " · " + str(row["score"]) + "/100 · " + str(row["vessel_count"]) + " vessels"
        alert_cards.append(
            '<div style="background:' + bg + ';padding:9px 12px;border-radius:6px;'
            'border-left:3px solid ' + bdr + ';">'
            '<div style="font-size:0.82rem;font-weight:700;color:' + tc + ';margin-bottom:3px">' + title + '</div>'
            '<p style="margin:0;font-size:0.78rem;color:' + bc + '">' + desc + '</p>'
            '<small style="color:' + sc + ';font-size:0.7rem;margin-top:3px;display:block">Just now</small>'
            '</div>'
        )

    if bdi.get("trend") == "rising" and len(alert_cards) < 3:
        bdi_desc = "BDI index " + str(bdi.get("value", "N/A")) + " · " + f"{bdi_chg:+.1f}%" + " today"
        alert_cards.append(
            '<div style="background:#fff9f0;padding:9px 12px;border-radius:6px;'
            'border-left:3px solid #ffb74d;">'
            '<div style="font-size:0.82rem;font-weight:700;color:#d97706;margin-bottom:3px">Freight Rate Rising</div>'
            '<p style="margin:0;font-size:0.78rem;color:#888">' + bdi_desc + '</p>'
            '<small style="color:#bbb;font-size:0.7rem;margin-top:3px;display:block">Just now</small>'
            '</div>'
        )

    for item in get_maritime_news(n=3 - len(alert_cards)):
        if len(alert_cards) >= 3:
            break
        url_a = 'href="' + item["url"] + '" target="_blank"' if item.get("url") else ""
        alert_cards.append(
            '<div style="background:#f0f6ff;padding:9px 12px;border-radius:6px;'
            'border-left:3px solid #90b8e8;">'
            '<div style="font-size:0.82rem;font-weight:600;color:#1a5296;margin-bottom:3px">'
            '<a ' + url_a + ' style="color:#1a5296;text-decoration:none;'
            'overflow:hidden;text-overflow:ellipsis;display:block;white-space:nowrap">'
            + str(item["title"]) + '</a></div>'
            '<p style="margin:0;font-size:0.78rem;color:#888">' + str(item["source"]) + '</p>'
            '<small style="color:#bbb;font-size:0.7rem;margin-top:3px;display:block">Maritime News</small>'
            '</div>'
        )

    if not alert_cards:
        alert_cards.append(
            '<div style="background:#f4fbf5;padding:9px 12px;border-radius:6px;'
            'border-left:3px solid #81c784;">'
            '<div style="font-size:0.82rem;font-weight:700;color:#2e7d32;margin-bottom:3px">All Systems Clear</div>'
            '<p style="margin:0;font-size:0.78rem;color:#888">No active congestion alerts</p>'
            '<small style="color:#bbb;font-size:0.7rem;margin-top:3px;display:block">All ports below threshold</small>'
            '</div>'
        )

    right_html = (
        '<div style="' + PANEL + 'margin-bottom:10px;">'
        '<h3 style="' + H3 + '">📍 Top Congested Ports</h3>'
        + "".join(port_rows) +
        '</div>'
        '<div style="' + PANEL + '">'
        '<h3 style="' + H3 + '">🔔 Live Alerts &amp; News</h3>'
        + "".join(alert_cards) +
        '</div>'
    )
    st.markdown(right_html, unsafe_allow_html=True)
