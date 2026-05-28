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

# ── Status pill ────────────────────────────────────────────────────────
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
age_str      = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching…"

if is_live:
    status_label, status_color, status_bg, status_border = \
        "System Operational", "#16a34a", "#f0fdf4", "#bbf7d0"
elif is_connected:
    status_label, status_color, status_bg, status_border = \
        "Data Stale", "#d97706", "#fffbeb", "#fde68a"
else:
    status_label, status_color, status_bg, status_border = \
        "Offline", "#dc2626", "#fef2f2", "#fecaca"

# ── Page header ────────────────────────────────────────────────────────
st.markdown(
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;'
    'padding-bottom:16px;border-bottom:1px solid #e5e7eb;">'
    '<div>'
    '<div style="color:#111827;font-size:22px;font-weight:800;'
    'letter-spacing:-0.02em;line-height:1.2">Supply Chain Intelligence</div>'
    '<div style="color:#6b7280;font-size:13px;margin-top:4px">'
    'Live port congestion &nbsp;·&nbsp; vessel tracking'
    ' &nbsp;·&nbsp; BDI freight analysis &nbsp;·&nbsp; '
    + str(len(ports)) + ' ports monitored'
    '</div>'
    '</div>'
    '<div style="display:flex;align-items:center;gap:14px;flex-shrink:0;">'
    '<span style="color:#6b7280;font-size:12px">🕐 Last sync: '
    '<b style="color:#374151">' + age_str + '</b></span>'
    '<div style="background:' + status_bg + ';border:1px solid ' + status_border + ';'
    'border-radius:20px;padding:5px 14px;display:flex;align-items:center;gap:6px;">'
    '<div style="width:7px;height:7px;border-radius:50%;background:' + status_color + '"></div>'
    '<span style="color:' + status_color + ';font-size:12px;font-weight:600">' + status_label + '</span>'
    '</div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ── KPI row — one continuous segmented container, no gaps between cards ─
bdi_border  = "#ef4444" if bdi_chg > 0 else "#22c55e" if bdi_chg < 0 else "#6b7280"
crit_border = "#ef4444" if critical_n > 0 else "#22c55e"
alrt_border = "#ef4444" if alert_count > 3 else "#f59e0b" if alert_count > 0 else "#22c55e"
crit_sub_c  = "#ef4444" if critical_n > 0 else "#22c55e"
alrt_sub_c  = "#ef4444" if alert_count > 3 else "#f59e0b" if alert_count > 0 else "#22c55e"
bdi_sub_c   = "#ef4444" if bdi_chg > 0 else "#22c55e" if bdi_chg < 0 else "#6b7280"

st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
    'border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;'
    'background:#ffffff;box-shadow:0 1px 3px rgba(0,0,0,0.08);">'

    '<div style="padding:20px 24px;border-left:4px solid #3b82f6;border-right:1px solid #e5e7eb;">'
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
    '<span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Vessels Tracked</span>'
    '<span style="font-size:20px;opacity:0.25">🚢</span>'
    '</div>'
    '<div style="color:#111827;font-size:28px;font-weight:800;line-height:1;margin-top:8px">' + f'{len(vessels):,}' + '</div>'
    '<div style="color:#6b7280;font-size:12px;margin-top:6px">across ' + str(len(ports)) + ' ports</div>'
    '</div>'

    '<div style="padding:20px 24px;border-left:4px solid ' + crit_border + ';border-right:1px solid #e5e7eb;">'
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
    '<span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Critical Ports</span>'
    '<span style="font-size:20px;opacity:0.25">⚓</span>'
    '</div>'
    '<div style="color:#111827;font-size:28px;font-weight:800;line-height:1;margin-top:8px">' + str(critical_n) + '</div>'
    '<div style="color:' + crit_sub_c + ';font-size:12px;margin-top:6px">' + str(high_n) + ' high risk</div>'
    '</div>'

    '<div style="padding:20px 24px;border-left:4px solid ' + alrt_border + ';border-right:1px solid #e5e7eb;">'
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
    '<span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Active Alerts</span>'
    '<span style="font-size:20px;opacity:0.25">⚠️</span>'
    '</div>'
    '<div style="color:#111827;font-size:28px;font-weight:800;line-height:1;margin-top:8px">' + str(alert_count) + '</div>'
    '<div style="color:' + alrt_sub_c + ';font-size:12px;margin-top:6px">$' + f'{alert_cost:.0f}' + 'M exposure</div>'
    '</div>'

    '<div style="padding:20px 24px;border-left:4px solid ' + bdi_border + ';">'
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
    '<span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">BDI</span>'
    '<span style="font-size:20px;opacity:0.25">📈</span>'
    '</div>'
    '<div style="color:#111827;font-size:28px;font-weight:800;line-height:1;margin-top:8px">' + str(bdi.get("value", "—")) + '</div>'
    '<div style="color:' + bdi_sub_c + ';font-size:12px;margin-top:6px">' + f'{bdi_chg:+.1f}%' + ' · ' + bdi.get("trend", "—").upper() + '</div>'
    '</div>'

    '</div>',
    unsafe_allow_html=True,
)

# ── Main content ───────────────────────────────────────────────────────
MAP_H = 480
# Light-friendly congestion dot colors (vivid, stand out on dark map)
LC = {"Clear": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444", "Critical": "#dc2626"}

map_col, right_col = st.columns([2, 1])

# ── Left: world map (dark navy map inside white panel) ─────────────────
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
        margin=dict(l=0, r=0, t=36, b=0),
        height=MAP_H,
        title=dict(
            text="🗺️  Port Congestion Map",
            font=dict(color="#111827", size=14),
            x=0.01, y=0.99, xanchor="left", yanchor="top",
        ),
        legend=dict(
            bgcolor="rgba(15,35,64,0.85)", bordercolor="rgba(255,255,255,0.1)",
            font=dict(color="#ffffff", size=11),
            orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0.02,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Right: two stacked white panel cards ──────────────────────────────
with right_col:
    CARD_GAP = "12px"
    PANEL = (
        'background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;'
        'padding:20px;display:flex;flex-direction:column;gap:' + CARD_GAP + ';'
        'box-shadow:0 1px 3px rgba(0,0,0,0.08);'
    )
    TITLE = 'color:#111827;font-size:15px;font-weight:700;margin:0;'

    # ── Port rows ───────────────────────────────────────────────────────
    port_rows = []
    for _, row in df_cong.head(2).iterrows():
        lc = LC.get(row.get("label", ""), "#6b7280")
        port_rows.append(
            '<div style="background:#f9fafb;border:1px solid #e5e7eb;'
            'border-left:4px solid ' + lc + ';border-radius:8px;'
            'padding:12px 16px;display:flex;align-items:center;">'
            '<div style="flex:1;min-width:0;">'
            '<div style="color:#111827;font-size:14px;font-weight:600;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
            + str(row["name"]) + '</div>'
            '<div style="color:#6b7280;font-size:12px;margin-top:3px">'
            + str(row["country"]) + ' · ' + str(row["vessel_count"]) + ' vessels'
            '</div>'
            '</div>'
            '<div style="flex-shrink:0;margin-left:12px;text-align:right;">'
            '<span style="color:' + lc + ';font-size:22px;font-weight:800">'
            + str(row["score"]) + '</span>'
            '<span style="color:#9ca3af;font-size:11px"> /100</span>'
            '</div>'
            '</div>'
        )
    if not port_rows:
        port_rows.append(
            '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:12px 16px;color:#9ca3af;font-size:13px">No congestion data yet</div>'
        )

    # ── Alert / news cards ───────────────────────────────────────────────
    # Light muted tints — clean corporate style matching reference
    alert_cards = []

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        if len(alert_cards) >= 3:
            break
        if row["score"] >= 86:
            bg, bdr, title_c = "#fef2f2", "#ef4444", "#dc2626"
            title = "Critical Congestion Detected"
        else:
            bg, bdr, title_c = "#fffbeb", "#f59e0b", "#d97706"
            title = "High Congestion Alert"
        desc = str(row["name"]) + " · " + str(row["score"]) + "/100 · " + str(row["vessel_count"]) + " vessels"
        alert_cards.append(
            '<div style="background:' + bg + ';border-left:4px solid ' + bdr + ';'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:' + title_c + ';font-size:14px;font-weight:700">' + title + '</div>'
            '<div style="color:#6b7280;font-size:13px;margin-top:4px">' + desc + '</div>'
            '<div style="color:#9ca3af;font-size:11px;margin-top:4px">Just now</div>'
            '</div>'
        )

    if bdi.get("trend") == "rising" and len(alert_cards) < 3:
        bdi_desc = "BDI index " + str(bdi.get("value", "N/A")) + " · " + f"{bdi_chg:+.1f}%" + " today"
        alert_cards.append(
            '<div style="background:#fffbeb;border-left:4px solid #f59e0b;'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:#d97706;font-size:14px;font-weight:700">Freight Rate Rising</div>'
            '<div style="color:#6b7280;font-size:13px;margin-top:4px">' + bdi_desc + '</div>'
            '<div style="color:#9ca3af;font-size:11px;margin-top:4px">Just now</div>'
            '</div>'
        )

    for item in get_maritime_news(n=3 - len(alert_cards)):
        if len(alert_cards) >= 3:
            break
        url_a = 'href="' + item["url"] + '" target="_blank"' if item.get("url") else ""
        alert_cards.append(
            '<div style="background:#eff6ff;border-left:4px solid #3b82f6;'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:#2563eb;font-size:14px;font-weight:700">'
            '<a ' + url_a + ' style="color:#2563eb;text-decoration:none;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block">'
            + str(item["title"]) + '</a></div>'
            '<div style="color:#6b7280;font-size:13px;margin-top:4px">' + str(item["source"]) + '</div>'
            '<div style="color:#9ca3af;font-size:11px;margin-top:4px">Maritime News</div>'
            '</div>'
        )

    if not alert_cards:
        alert_cards.append(
            '<div style="background:#f0fdf4;border-left:4px solid #22c55e;'
            'border-radius:8px;padding:12px 16px;">'
            '<div style="color:#16a34a;font-size:14px;font-weight:700">All Systems Clear</div>'
            '<div style="color:#6b7280;font-size:13px;margin-top:4px">No active congestion alerts</div>'
            '<div style="color:#9ca3af;font-size:11px;margin-top:4px">All ports below threshold</div>'
            '</div>'
        )

    right_html = (
        '<div style="' + PANEL + 'margin-bottom:16px;">'
        '<div style="' + TITLE + '">📍 Top Congested Ports</div>'
        + "".join(port_rows) +
        '</div>'
        '<div style="' + PANEL + '">'
        '<div style="' + TITLE + '">🔔 Live Alerts &amp; News</div>'
        + "".join(alert_cards) +
        '</div>'
    )
    st.markdown(right_html, unsafe_allow_html=True)
