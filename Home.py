import json
import os
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from services.news import get_maritime_news
from db import cache, supabase_logger
from components.styles import inject_global_css, navbar

load_dotenv()

# Auto-refresh every 10 minutes (600 000 ms).
# Each cycle fetches fresh AIS data and logs a Supabase snapshot.
st_autorefresh(interval=10 * 60 * 1000, key="dashboard_refresh")

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

# Log to Supabase on every page load — log_snapshot() deduplicates internally
# (skips insert if a row was already written in the last 10 minutes).
# Must stay in the main Streamlit thread; st.secrets fails in background threads.
if vessel_count > 0:
    try:
        supabase_logger.log_snapshot(vessel_count)
    except Exception:
        pass

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

# ── Fleet Activity Cards ────────────────────────────────────────────────
_daily  = supabase_logger.get_daily_activity(7)
_h24    = supabase_logger.get_last_24h_activity()

_CF = dict(family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif",
           color="#64748b", size=10)
_CL = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font=_CF,
    margin=dict(l=36, r=10, t=32, b=24), height=190,
    xaxis=dict(showgrid=False, zeroline=False, tickfont=_CF,
               linecolor="#e2e8f0", tickcolor="#e2e8f0"),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9", zeroline=False,
               tickfont=_CF, linecolor="#e2e8f0"),
    showlegend=False,
)
_PH = (
    '<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;'
    'height:190px;display:flex;flex-direction:column;align-items:center;'
    'justify-content:center;gap:6px;">'
    '<div style="font-size:26px">{icon}</div>'
    '<div style="color:#1e293b;font-size:13px;font-weight:700">Collecting Data</div>'
    '<div style="color:#94a3b8;font-size:11px;text-align:center;max-width:200px">'
    '{label}<br>Check back in a few hours</div></div>'
)

_ac_left, _ac_right = st.columns(2)

with _ac_left:
    if _daily:
        _fig7 = go.Figure(go.Scatter(
            x=[str(r["day"]) for r in _daily],
            y=[float(r["avg_total"]) for r in _daily],
            mode="lines+markers",
            line=dict(color="#3b82f6", width=2.5),
            marker=dict(color="#3b82f6", size=5),
            fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
            hovertemplate="%{x}<br><b>%{y:.0f} vessels</b><extra></extra>",
        ))
        _fig7.update_layout(
            **{k: v for k, v in _CL.items() if k != "xaxis"},
            title=dict(text="<b>Fleet Activity — Last 7 Days</b>",
                       font=dict(color="#1e293b", size=12), x=0, xanchor="left"),
            xaxis=dict(**_CL["xaxis"], tickformat="%b %d", dtick=86400000),
        )
        st.plotly_chart(_fig7, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(_PH.format(icon="📡", label="Fleet Activity — Last 7 Days"),
                    unsafe_allow_html=True)

with _ac_right:
    if _h24:
        _fig24 = go.Figure(go.Scatter(
            x=[str(r["logged_at"]) for r in _h24],
            y=[r["total"] for r in _h24],
            mode="lines",
            line=dict(color="#22c55e", width=2.5),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.08)",
            hovertemplate="%{x}<br><b>%{y} vessels</b><extra></extra>",
        ))
        _fig24.update_layout(
            **{k: v for k, v in _CL.items() if k != "xaxis"},
            title=dict(text="<b>Fleet Activity — Last 24 Hours</b>",
                       font=dict(color="#1e293b", size=12), x=0, xanchor="left"),
            xaxis=dict(**_CL["xaxis"], tickformat="%H:00", dtick=3600000),
        )
        st.plotly_chart(_fig24, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(_PH.format(icon="🕐", label="Fleet Activity — Last 24 Hours"),
                    unsafe_allow_html=True)

st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

# ── Main content — rendered as one components.html block ───────────────
# components.html() renders inside an iframe where we own the full DOM.
# This is the only reliable way to get border-radius clipping + equal-height
# columns in Streamlit — CSS selectors on Streamlit's emotion-wrapped divs
# cannot reliably override internal stacking contexts and intermediate padding.

LC    = {"Clear": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444", "Critical": "#dc2626"}
PANEL = (
    'background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;'
    'padding:16px;display:flex;flex-direction:column;gap:10px;'
)
# Ports panel uses tighter padding + gap so 3 compact cards fit comfortably
PORTS_PANEL = (
    'background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;'
    'padding:12px 14px;display:flex;flex-direction:column;gap:6px;'
)
TITLE = 'color:#1e293b;font-size:15px;font-weight:700;margin-bottom:2px;'

# ── Build Plotly figure ─────────────────────────────────────────────────
SECTION_H = 500   # section height; map fills left card, right panels fill right col

fig = go.Figure()
if not df_cong.empty:
    for label, color in LC.items():
        sub = df_cong[df_cong["label"] == label]
        if sub.empty:
            continue
        # Legend-only phantom trace — fixed size so all dots look equal in the legend
        fig.add_trace(go.Scattergeo(
            lat=[None], lon=[None],
            mode="markers",
            name=label,
            marker=dict(size=10, color=color, opacity=0.85),
            showlegend=True,
        ))
        # Real data trace — score-sized markers, no legend entry
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
            showlegend=False,
            hovertext=sub.apply(
                lambda r: f"<b>{r['name']}</b><br>Score: {r['score']}/100 — {r['label']}<br>Vessels: {r['vessel_count']}",
                axis=1,
            ).tolist(),
            hovertemplate="%{hovertext}<extra></extra>",
        ))
fig.update_layout(
    geo=dict(
        projection_type="natural earth",
        projection_scale=1.0,
        center=dict(lon=10, lat=15),
        showland=True,      landcolor="#dde8ef",
        showocean=True,     oceancolor="#ffffff",
        showlakes=False,
        showcountries=True, countrycolor="#94a3b8",
        showframe=False,    bgcolor="#ffffff",
        lataxis=dict(range=[-60, 80]),
        lonaxis=dict(range=[-170, 190]),
    ),
    paper_bgcolor="#ffffff",
    margin=dict(l=0, r=0, t=40, b=0),
    height=SECTION_H,
    title=dict(
        text="<b>Port Congestion Map</b>",
        font=dict(color="#1e293b", size=14, family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"),
        x=0.01, xanchor="left",
        y=0.98, yanchor="top",
    ),
    legend=dict(
        bgcolor="#ffffff", bordercolor="#e2e8f0",
        font=dict(color="#64748b", size=11),
        orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.0,
        itemsizing="constant",   # force equal icon size regardless of marker data
    ),
)

# Serialize figure to HTML fragment (CDN plotly.js, scripts execute inside iframe)
chart_html = pio.to_html(
    fig,
    include_plotlyjs="cdn",
    full_html=False,
    config={"displayModeBar": False, "scrollZoom": False, "responsive": True},
)

# ── Build right-panel HTML ──────────────────────────────────────────────
port_html = ""
for _, row in df_cong.head(3).iterrows():
    lc = LC.get(row.get("label", ""), "#64748b")
    port_html += (
        f'<div style="background:#f8fafc;border-radius:8px;padding:8px 12px;'
        f'display:flex;align-items:center;">'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="color:#1e293b;font-size:13px;font-weight:600;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{row["name"]}</div>'
        f'<div style="color:#94a3b8;font-size:11px;margin-top:2px">'
        f'{row["country"]} · {row["vessel_count"]} vessels</div>'
        f'</div>'
        f'<div style="flex-shrink:0;margin-left:10px;">'
        f'<span style="color:#1e293b;font-size:19px;font-weight:800">{row["score"]}</span>'
        f'<span style="color:#94a3b8;font-size:10px"> /100</span>'
        f'</div>'
        f'</div>'
    )
if not port_html:
    port_html = (
        '<div style="background:#f8fafc;border-radius:8px;padding:8px 12px;'
        'color:#94a3b8;font-size:13px">No congestion data yet</div>'
    )

def _alert_card(bg: str, col: str, title: str, body: str, timestamp: str = "Just now") -> str:
    return (
        f'<div style="background:{bg};border-radius:10px;padding:12px 14px;">'
        f'<div style="color:{col};font-size:13px;font-weight:700">{title}</div>'
        f'<div style="color:#475569;font-size:12px;margin-top:3px">{body}</div>'
        f'<div style="color:#94a3b8;font-size:11px;margin-top:3px">{timestamp}</div>'
        f'</div>'
    )

# Cycling palette for news cards so consecutive items look distinct
_NEWS_PALETTE = [
    ("#eff6ff", "#3b82f6"),   # blue
    ("#f5f3ff", "#7c3aed"),   # violet
    ("#ecfeff", "#0891b2"),   # cyan
]

alert_html = ""
n_cards = 0

for _, row in df_cong[df_cong["score"] >= 60].head(2).iterrows():
    if n_cards >= 3:
        break
    is_crit = row["score"] >= 86
    col     = "#ef4444" if is_crit else "#f59e0b"
    bg      = "#fef2f2" if is_crit else "#fffbeb"
    title   = "Critical Congestion Detected" if is_crit else "High Congestion Alert"
    body    = f'{row["name"]} · {row["score"]}/100 · {row["vessel_count"]} vessels'
    alert_html += _alert_card(bg, col, title, body)
    n_cards += 1

if bdi.get("trend") == "rising" and n_cards < 3:
    body = f'BDI index {bdi.get("value","N/A")} · {bdi_chg:+.1f}% today'
    alert_html += _alert_card("#fffbeb", "#f59e0b", "Freight Rate Rising", body)
    n_cards += 1

for item in news_items[:3 - n_cards]:
    if n_cards >= 3:
        break
    bg, col = _NEWS_PALETTE[n_cards % len(_NEWS_PALETTE)]
    url_a   = f'href="{item["url"]}" target="_blank"' if item.get("url") else ""
    title_a = (
        f'<a {url_a} style="color:{col};text-decoration:none;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block">'
        f'{item["title"]}</a>'
    )
    alert_html += (
        f'<div style="background:{bg};border-radius:10px;padding:12px 14px;">'
        f'<div style="color:{col};font-size:13px;font-weight:700">{title_a}</div>'
        f'<div style="color:#475569;font-size:12px;margin-top:3px">{item["source"]}</div>'
        f'<div style="color:#94a3b8;font-size:11px;margin-top:3px">Maritime News</div>'
        f'</div>'
    )
    n_cards += 1

if not alert_html:
    alert_html = _alert_card(
        "#f0fdf4", "#22c55e",
        "All Systems Clear",
        "No active congestion alerts",
        "All ports below threshold",
    )

# ── Render as single iframe — full CSS control, no Streamlit wrappers ──
section_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{
    width:100%;height:{SECTION_H}px;
    background:transparent;overflow:hidden;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
}}
.cp-row{{
    display:flex;
    gap:12px;
    height:100%;
    align-items:stretch;
}}
/* Map card — border-radius works here because we own the DOM */
.cp-map{{
    flex:3;min-width:0;
    background:#ffffff;
    border:1px solid #e2e8f0;
    border-radius:16px;
    overflow:hidden;
    box-shadow:0 1px 3px rgba(0,0,0,0.04);
}}
.cp-map>div{{height:100%;}}
/* Right column */
.cp-right{{
    flex:2;min-width:0;
    display:flex;
    flex-direction:column;
    gap:10px;
    height:100%;
}}
.cp-right-top{{flex-shrink:0;}}
.cp-right-bot{{flex:1;display:flex;flex-direction:column;}}
.cp-right-bot>div:last-child{{flex:1;}}
</style>
</head>
<body>
<div class="cp-row">
    <div class="cp-map">{chart_html}</div>
    <div class="cp-right">
        <div class="cp-right-top">
            <div style="{PORTS_PANEL}">
                <div style="{TITLE}">📍 Top Congested Ports</div>
                {port_html}
            </div>
        </div>
        <div class="cp-right-bot">
            <div style="{PANEL}flex:1;overflow:hidden;">
                <div style="{TITLE}">🔔 Live Alerts &amp; News</div>
                {alert_html}
            </div>
        </div>
    </div>
</div>
<script>
/* Force Plotly to re-measure the container after the iframe finishes painting.
   Without this, responsive:true may snapshot width=0 and render off-centre. */
function resizePlot() {{
    var el = document.querySelector('.js-plotly-plot');
    if (window.Plotly && el) {{
        Plotly.Plots.resize(el);
    }}
}}
/* Fire on load and once more after a short delay to catch late CDN load */
window.addEventListener('load', function() {{
    resizePlot();
    setTimeout(resizePlot, 400);
}});
</script>
</body>
</html>"""

components.html(section_html, height=SECTION_H + 2, scrolling=False)
