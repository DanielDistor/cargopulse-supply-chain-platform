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

# Count only vessels with valid coordinates (consistent with Vessel Tracking page)
vessel_count = sum(1 for v in (vessels or []) if v.get("lat") is not None and v.get("lon") is not None)

critical_n  = int((df_cong["score"] >= 86).sum()) if not df_cong.empty else 0
high_n      = int(((df_cong["score"] >= 61) & (df_cong["score"] < 86)).sum()) if not df_cong.empty else 0
alert_count = int((df_cong["score"] >= 60).sum()) + (1 if bdi.get("trend") == "rising" else 0)
alert_cost  = round(sum(
    next((p["capacity_baseline"] for p in ports if p["name"] == row["name"]), 30)
    * row["score"] / 100 * 0.35
    for _, row in df_cong[df_cong["score"] >= 60].iterrows()
), 0) if not df_cong.empty else 0
bdi_chg    = bdi.get("change_pct_1d") or 0
bdi_val    = bdi.get("value")
bdi_display = f"{bdi_val:,.0f}" if bdi_val is not None else "N/A"

# ── Page header ────────────────────────────────────────────────────────
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900
age_str      = f"{vessel_age // 60}m {vessel_age % 60}s ago" if vessel_age else "fetching…"

if is_live:
    status_label, status_color = "System Operational", "#22c55e"
elif is_connected:
    status_label, status_color = "Data Stale",         "#f59e0b"
else:
    status_label, status_color = "Offline",            "#ef4444"

st.markdown(
    f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding-bottom:12px;border-bottom:1px solid #e2e8f0;">
        <div>
            <div style="color:#1e293b;font-size:22px;font-weight:800;
                        letter-spacing:-0.02em;line-height:1.2">Supply Chain Intelligence</div>
            <div style="color:#94a3b8;font-size:13px;margin-top:4px">
                Live port congestion &nbsp;·&nbsp; vessel tracking
                &nbsp;·&nbsp; BDI freight analysis &nbsp;·&nbsp; {len(ports)} ports monitored
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:14px;flex-shrink:0;">
            <span style="color:#94a3b8;font-size:12px">🕐 Last sync:
                <b style="color:#64748b">{age_str}</b></span>
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
def _kpi(label, value, sub, sub_color="#64748b", border_color=None, icon=""):
    bl = f"border-left:4px solid {border_color};" if border_color else ""
    ic = f'<span style="font-size:22px;opacity:0.6;line-height:1">{icon}</span>' if icon else ""
    return (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;{bl}'
        f'border-radius:10px;padding:16px 20px;height:90px;'
        f'display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
        f'<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{label}</div>'
        f'{ic}</div>'
        f'<div style="color:#1e293b;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{sub_color};font-size:12px">{sub}</div>'
        f'</div>'
    )

bdi_color   = "#ef4444" if bdi_chg > 0 else "#22c55e" if bdi_chg < 0 else "#64748b"
crit_color  = "#ef4444" if critical_n > 0 else "#22c55e"
alert_color = "#ef4444" if alert_count > 3 else "#f59e0b" if alert_count > 0 else "#22c55e"

c1, c2, c3, c4 = st.columns(4)
c1.markdown(_kpi("Vessels Tracked",  f"{vessel_count:,}",        f"across {len(ports)} ports",     "#64748b",   "#3b82f6", "🚢"), unsafe_allow_html=True)
c2.markdown(_kpi("Critical Ports",   str(critical_n),            f"{high_n} high risk",            crit_color,  "#ef4444" if critical_n > 0 else "#22c55e", "⚓"), unsafe_allow_html=True)
c3.markdown(_kpi("Active Alerts",    str(alert_count),           f"${alert_cost:.0f}M exposure",   alert_color, "#ef4444" if alert_count > 0 else "#22c55e", "⚠️"), unsafe_allow_html=True)
c4.markdown(_kpi("BDI",             bdi_display,                 f"{bdi_chg:+.1f}% · {bdi.get('trend','unknown').upper()}", bdi_color, bdi_color, "📈"), unsafe_allow_html=True)

# Spacer so KPI row doesn't visually bleed into the panels below
st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

# ── Map card CSS — injected before the columns so selectors are live ───
st.markdown(
    """
    <style>
    /* Target only the row that contains the Plotly chart */

    /* Stretch both columns to the same height so map bottom = right panel bottom */
    [data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"]) {
        align-items: stretch !important;
    }

    /* Left column IS the card — apply border/radius here, not on the inner chart */
    [data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"])
    > [data-testid="stColumn"]:first-child {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        padding: 0 !important;
        display: flex;
        flex-direction: column;
    }

    /* Strip inner Plotly chart border/radius — column handles it */
    [data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"])
    [data-testid="stPlotlyChart"] {
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        margin: 0 !important;
        background: #ffffff;
    }

    /* Right column: flex column so stacked panels fill naturally */
    [data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"])
    > [data-testid="stColumn"]:last-child {
        display: flex !important;
        flex-direction: column !important;
        padding: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Main content ───────────────────────────────────────────────────────
MAP_H = 520

map_col, right_col = st.columns([3, 2])
LC = {"Clear": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444", "Critical": "#dc2626"}

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
            showland=True,      landcolor="#dde8ef",
            showocean=True,     oceancolor="#ffffff",
            showlakes=False,
            showcountries=True, countrycolor="#94a3b8",
            showframe=False,    bgcolor="#ffffff",
        ),
        paper_bgcolor="#ffffff",
        margin=dict(l=0, r=0, t=30, b=0),
        height=MAP_H,
        title=dict(text="Port Congestion Map", font=dict(color="#64748b", size=12), x=0),
        legend=dict(
            bgcolor="#ffffff", bordercolor="#e2e8f0",
            font=dict(color="#64748b", size=11),
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
        f'background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;'
        f'padding:16px;display:flex;flex-direction:column;gap:{GAP};'
    )
    TITLE = 'color:#1e293b;font-size:15px;font-weight:700;'

    # ── Port rows ───────────────────────────────────────────────────────
    port_html = ""
    for _, row in df_cong.head(2).iterrows():
        lc = LC.get(row.get("label", ""), "#64748b")
        port_html += (
            f'<div style="background:#f8fafc;border-radius:10px;padding:14px 16px;'
            f'display:flex;align-items:center;border-left:3px solid {lc};">'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="color:#1e293b;font-size:14px;font-weight:600;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
            f'<div style="color:#94a3b8;font-size:12px;margin-top:4px">'
            f'{row["country"]} · {row["vessel_count"]} vessels</div>'
            f'</div>'
            f'<div style="flex-shrink:0;margin-left:12px;">'
            f'<span style="color:{lc};font-size:22px;font-weight:800">{row["score"]}</span>'
            f'<span style="color:#94a3b8;font-size:11px"> /100</span>'
            f'</div>'
            f'</div>'
        )
    if not port_html:
        port_html = (
            '<div style="background:#f8fafc;border-radius:10px;padding:14px 16px;'
            'color:#94a3b8;font-size:13px">No congestion data yet</div>'
        )

    # ── Alert / news cards — match reference style exactly ─────────────
    # Reference: colored tint background, NO left border, bold colored title,
    # description line, small gray timestamp. No badge — just the title text.
    alert_html = ""
    n_cards = 0

    for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
        if n_cards >= 3:
            break
        is_crit = row["score"] >= 86
        col     = "#ef4444" if is_crit else "#f59e0b"
        bg      = "#fef2f2" if is_crit else "#fffbeb"
        title   = f'Critical Congestion Detected' if is_crit else f'High Congestion Alert'
        alert_html += (
            f'<div style="background:{bg};border-radius:10px;padding:14px 16px;">'
            f'<div style="color:{col};font-size:13px;font-weight:700">{title}</div>'
            f'<div style="color:#475569;font-size:12px;margin-top:4px">'
            f'{row["name"]} · {row["score"]}/100 · {row["vessel_count"]} vessels</div>'
            f'<div style="color:#94a3b8;font-size:11px;margin-top:4px">Just now</div>'
            f'</div>'
        )
        n_cards += 1

    if bdi.get("trend") == "rising" and n_cards < 3:
        alert_html += (
            f'<div style="background:#fffbeb;border-radius:10px;padding:14px 16px;">'
            f'<div style="color:#f59e0b;font-size:13px;font-weight:700">Freight Rate Rising</div>'
            f'<div style="color:#475569;font-size:12px;margin-top:4px">'
            f'BDI index {bdi.get("value","N/A")} · {bdi_chg:+.1f}% today</div>'
            f'<div style="color:#94a3b8;font-size:11px;margin-top:4px">Just now</div>'
            f'</div>'
        )
        n_cards += 1

    for item in news_items[:3 - n_cards]:
        if n_cards >= 3:
            break
        url_a = f'href="{item["url"]}" target="_blank"' if item.get("url") else ""
        alert_html += (
            f'<div style="background:#eff6ff;border-radius:10px;padding:14px 16px;">'
            f'<div style="color:#3b82f6;font-size:13px;font-weight:700">'
            f'<a {url_a} style="color:#3b82f6;text-decoration:none;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block">'
            f'{item["title"]}</a></div>'
            f'<div style="color:#475569;font-size:12px;margin-top:4px">{item["source"]}</div>'
            f'<div style="color:#94a3b8;font-size:11px;margin-top:4px">Maritime News</div>'
            f'</div>'
        )
        n_cards += 1

    if not alert_html:
        alert_html = (
            '<div style="background:#f0fdf4;border-radius:10px;padding:14px 16px;">'
            '<div style="color:#22c55e;font-size:13px;font-weight:700">All Systems Clear</div>'
            '<div style="color:#475569;font-size:12px;margin-top:4px">No active congestion alerts</div>'
            '<div style="color:#94a3b8;font-size:11px;margin-top:4px">All ports below threshold</div>'
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
