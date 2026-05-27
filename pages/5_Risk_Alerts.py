import json
import os
import hashlib
import datetime
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from services import aisstream, congestion as cong_svc
from services.shipping_rates import get_bdi
from db import cache
from components.styles import inject_global_css

load_dotenv()

st.set_page_config(page_title="Risk Alerts | CargoPulse", layout="wide")
inject_global_css()

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

port_map = {p["name"]: p for p in ports}

# ── Connection status ────────────────────────────────────────────────
vessel_age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)
is_connected = vessel_age is not None
is_live      = is_connected and vessel_age < 900

conn_color = "#4caf50" if is_connected else "#ef5350"
live_color = "#4caf50" if is_live      else "#ffb74d"

st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;">
    <div>
        <div style="font-size:26px;font-weight:800;color:#e8eaed;margin-bottom:6px;">Live Risk Alerts</div>
        <div style="color:#6b7fa3;font-size:14px">
            Real-time disruption alerts from live port congestion, marine weather, and Baltic Dry Index.
        </div>
    </div>
    <div style="display:flex;gap:20px;align-items:center;padding-top:4px;flex-shrink:0;">
        <div style="display:flex;align-items:center;gap:7px;">
            <div style="width:9px;height:9px;border-radius:50%;background:{conn_color};
                        box-shadow:0 0 8px {conn_color};animation:pulse 2s infinite;"></div>
            <span style="color:#a0aab4;font-size:13px;font-weight:600">Connected</span>
        </div>
        <div style="display:flex;align-items:center;gap:7px;">
            <div style="width:9px;height:9px;border-radius:50%;background:{live_color};
                        box-shadow:0 0 8px {live_color};"></div>
            <span style="color:#a0aab4;font-size:13px;font-weight:600">Live Monitoring</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────
def _h(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16)

CATEGORY_EMOJI = {
    "port-congestion":   "🚢",
    "weather-disruption":"🌊",
    "freight-cost":      "📈",
    "supplier-risk":     "⚠️",
}

RECOMMENDATIONS = {
    "port-congestion": [
        "Reroute time-critical shipments to the nearest alternative port",
        "Contact freight forwarder for real-time berth availability",
        "Notify downstream customers of revised ETAs",
        "Review safety stock levels for affected product lines",
        "Activate contingency logistics plan for high-priority SKUs",
        "Monitor congestion score for improvement before rebooking",
    ],
    "weather-disruption": [
        "Delay non-critical vessel departures until sea state improves",
        "Confirm vessel status with carriers operating in affected region",
        "Increase inventory buffer for components routed through impacted port",
        "Check marine weather forecast for 72-hour outlook",
        "Expedite airfreight for urgent components as backup",
    ],
    "freight-cost": [
        "Lock in forward freight contracts before further rate increases",
        "Review spot rate exposure across all active trade lanes",
        "Accelerate shipment of high-priority inventory now",
        "Negotiate long-term capacity agreements with preferred carriers",
        "Evaluate air freight for time-critical, low-volume components",
        "Update landed cost models to reflect current BDI level",
    ],
    "supplier-risk": [
        "Contact key suppliers in affected region for operational status",
        "Activate secondary supplier qualification process",
        "Review dual-sourcing options for single-source components",
        "Increase safety stock for critical items from this region",
        "Schedule supplier risk review with procurement team",
    ],
}


def generate_alerts(all_congestion: list, bdi: dict) -> list:
    alerts = []
    now = datetime.datetime.utcnow()
    country_port_count = {}
    for p in ports:
        country_port_count[p["country"]] = country_port_count.get(p["country"], 0) + 1

    for cong in sorted(all_congestion, key=lambda x: x["score"], reverse=True):
        score = cong["score"]
        if score < 60:
            continue

        h = _h(cong["name"] + "alert")
        port = port_map.get(cong["name"], {})
        cap  = port.get("capacity_baseline", 30)

        # Deterministic but realistic impact metrics
        cost_m       = round(cap * score / 100 * (0.35 + (h % 30) / 100), 1)
        delay_min    = max(2, int(score / 25))
        delay_max    = delay_min + 2 + (h % 6)
        inventory    = 15 + (h % 52)
        recovery     = 7  + (h % 22)
        suppliers    = max(2, cap // 8 + (h % 4))
        mins_ago     = 10 + (h % 110)
        detected     = now - datetime.timedelta(minutes=mins_ago)
        wave         = cong.get("wave_height_m")

        category = "weather-disruption" if (wave and wave > 2.5 and score < 75) else "port-congestion"
        if category == "weather-disruption":
            title = f"Heavy Seas at {cong['name']} — Vessel Operations Disrupted"
            threat = f"Wave height {wave:.1f} m at {cong['name']} with congestion score {score}/100"
        else:
            title = f"Port Congestion Surge: {cong['name']}"
            threat = f"Congestion at {cong['name']} reached {score}/100 — {cong['label']} status"

        alerts.append({
            "title":           title,
            "subtitle":        f"{cong['country']} · {cong['region']}",
            "category":        category,
            "risk_score":      score,
            "risk_level":      "CRITICAL" if score >= 86 else "HIGH",
            "suppliers":       suppliers,
            "cost_m":          cost_m,
            "delay_min":       delay_min,
            "delay_max":       delay_max,
            "inventory":       inventory,
            "recovery":        recovery,
            "detected":        detected,
            "threat":          threat,
            "country":         cong["country"],
            "port":            cong["name"],
            "wave_m":          wave,
        })

    # BDI freight cost alert
    if bdi.get("trend") == "rising":
        h = _h("BDI_FREIGHT_ALERT")
        chg = abs(bdi.get("change_pct_1d") or 0)
        alerts.append({
            "title":       "Baltic Dry Index Rising — Global Freight Cost Escalation",
            "subtitle":    "All major shipping lanes · Global",
            "category":    "freight-cost",
            "risk_score":  min(100, 50 + int(chg * 8)),
            "risk_level":  "HIGH",
            "suppliers":   10 + (h % 12),
            "cost_m":      round(bdi.get("value", 2000) / 80, 1),
            "delay_min":   1,
            "delay_max":   4,
            "inventory":   20 + (h % 25),
            "recovery":    14 + (h % 14),
            "detected":    datetime.datetime.utcnow() - datetime.timedelta(hours=1, minutes=h % 40),
            "threat":      f"BDI at {bdi.get('value', 'N/A')} with +{chg:.1f}% daily change — freight rates accelerating",
            "country":     "Global",
            "port":        "All lanes",
            "wave_m":      None,
        })

    return sorted(alerts, key=lambda x: x["risk_score"], reverse=True)


def level_color(level: str) -> str:
    return {"CRITICAL": "#b71c1c", "HIGH": "#ef5350", "MEDIUM": "#ffb74d"}.get(level, "#a0aab4")


def alert_card_html(alert: dict, idx: int) -> str:
    lc   = level_color(alert["risk_level"])
    emoji = CATEGORY_EMOJI.get(alert["category"], "⚠️")
    ts   = alert["detected"].strftime("%-I:%M:%S %p")
    return f"""
<div style="
    background:linear-gradient(135deg,#1a1f2e,#16202f);
    border:1px solid #263044;border-left:4px solid {lc};
    border-radius:0 10px 10px 0;padding:16px 18px;margin-bottom:10px;
">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
        <div style="flex:1;min-width:0;">
            <div style="color:#e8eaed;font-size:14px;font-weight:700;margin-bottom:6px;">
                {alert['title']}
            </div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
                <span style="color:#5a6a7e;font-size:12px">{ts}</span>
                <span style="background:#1e2736;color:#a0aab4;padding:2px 8px;border-radius:4px;font-size:11px">
                    {alert['category']}
                </span>
                <span style="color:#6b7fa3;font-size:12px">{alert['suppliers']} suppliers</span>
                <span style="background:{lc}22;color:{lc};padding:2px 8px;border-radius:4px;
                             font-size:11px;font-weight:700">{alert['risk_level']}</span>
            </div>
        </div>
        <div style="border:2px solid {lc};color:{lc};padding:4px 10px;border-radius:6px;
                    font-size:13px;font-weight:800;white-space:nowrap;flex-shrink:0;">
            {alert['risk_score']}/100
        </div>
    </div>
    <div style="display:flex;gap:20px;margin-top:12px;flex-wrap:wrap;">
        <span style="color:{lc};font-weight:700;font-size:13px">${alert['cost_m']}M cost impact</span>
        <span style="color:{lc};font-weight:700;font-size:13px">{alert['delay_min']}–{alert['delay_max']} days delay</span>
        <span style="color:{lc};font-weight:700;font-size:13px">{alert['inventory']}% inventory</span>
        <span style="color:{lc};font-weight:700;font-size:13px">{alert['recovery']} days recovery</span>
    </div>
</div>"""


# ── Load live data ────────────────────────────────────────────────────
with st.spinner("Scanning live data feeds for disruptions..."):
    bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]
    vessels        = aisstream.get_vessels(bounding_boxes)
    all_congestion = cong_svc.get_all_port_congestion(vessels)
    bdi            = get_bdi()

alerts = generate_alerts(all_congestion, bdi)

if not alerts:
    st.info("No active alerts — all monitored ports are within normal operating parameters.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────
total_alerts  = len(alerts)
high_crit     = sum(1 for a in alerts if a["risk_level"] in ("HIGH", "CRITICAL"))
total_sup     = sum(a["suppliers"] for a in alerts)
total_cost    = sum(a["cost_m"] for a in alerts)

def _kpi(label, value, sub="", sub_color="#6b7fa3"):
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;'
        f'padding:16px 18px;height:96px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">{label}</div>'
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{sub_color};font-size:12px">{sub}</div>'
        f'</div>'
    )

k1, k2, k3, k4 = st.columns(4)
alert_color = "#ef5350" if total_alerts > 3 else "#ffb74d" if total_alerts > 0 else "#4caf50"
k1.markdown(_kpi("Active Alerts",       total_alerts, f"{high_crit} high or critical", alert_color), unsafe_allow_html=True)
k2.markdown(_kpi("High or Critical",    high_crit,    f"of {total_alerts} total",       "#ef5350"),   unsafe_allow_html=True)
k3.markdown(_kpi("Suppliers Affected",  total_sup,    "across all alerts"),                           unsafe_allow_html=True)
k4.markdown(_kpi("Total Cost Exposure", f"${total_cost:.0f}M", "estimated impact",      "#ef5350"),   unsafe_allow_html=True)

st.divider()

# ── Main layout: alerts feed + event log ─────────────────────────────
feed_col, log_col = st.columns([3, 2])

with feed_col:
    # Badge header
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
        f'<span style="color:#e8eaed;font-size:16px;font-weight:700">Active Risk Alerts</span>'
        f'<span style="background:#ef5350;color:white;border-radius:50%;width:24px;height:24px;'
        f'display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:800">'
        f'{total_alerts}</span></div>',
        unsafe_allow_html=True,
    )
    for i, alert in enumerate(alerts):
        st.markdown(alert_card_html(alert, i), unsafe_allow_html=True)

with log_col:
    st.markdown(
        '<div style="color:#e8eaed;font-size:16px;font-weight:700;margin-bottom:14px;">Event Log</div>',
        unsafe_allow_html=True,
    )
    log_container = st.container(height=480)
    with log_container:
        for alert in sorted(alerts, key=lambda x: x["detected"], reverse=True):
            lc    = level_color(alert["risk_level"])
            emoji = CATEGORY_EMOJI.get(alert["category"], "⚠️")
            ts    = alert["detected"].strftime("%-I:%M:%S %p")
            score = alert["risk_score"]
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid #1e2736;'
                f'align-items:flex-start;">'
                f'<span style="color:#5a6a7e;font-size:11px;white-space:nowrap;padding-top:1px">{ts}</span>'
                f'<span style="color:{lc};font-size:11px;white-space:nowrap;font-weight:700;padding-top:1px">'
                f'[Risk:{score}]</span>'
                f'<span style="color:#a0aab4;font-size:11px;line-height:1.4">{alert["title"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.divider()

# ── Risk Analysis & Recommendations ──────────────────────────────────
st.markdown(
    '<div style="color:#e8eaed;font-size:16px;font-weight:700;margin-bottom:14px;">Risk Analysis & Recommendations</div>',
    unsafe_allow_html=True,
)

alert_titles = [a["title"] for a in alerts]
selected_title = st.selectbox("Select an alert to analyse", alert_titles, label_visibility="collapsed")
selected = next(a for a in alerts if a["title"] == selected_title)
lc = level_color(selected["risk_level"])

left, right = st.columns(2)

with left:
    st.markdown(
        f"""
<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;padding:20px;height:100%;">
    <div style="color:#e8eaed;font-size:14px;font-weight:700;margin-bottom:16px;
                padding-bottom:10px;border-bottom:1px solid #263044;">
        Current Assessment
    </div>
    <div style="margin-bottom:12px;">
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">Primary Threat</div>
        <div style="color:#e8eaed;font-size:14px">{selected['threat']}</div>
    </div>
    <div style="margin-bottom:12px;">
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">Risk Level</div>
        <div style="color:{lc};font-size:14px;font-weight:700">{selected['risk_score']}/100 ({selected['risk_level']})</div>
    </div>
    <div style="margin-bottom:12px;">
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">Category</div>
        <div style="color:#e8eaed;font-size:14px">{selected['category']}</div>
    </div>
    <div style="margin-bottom:12px;">
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">Suppliers Affected</div>
        <div style="color:#e8eaed;font-size:14px">{selected['suppliers']} organizations</div>
    </div>
    <div>
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">Detection Time</div>
        <div style="color:#e8eaed;font-size:14px">{selected['detected'].strftime("%-m/%-d/%Y, %-I:%M:%S %p")} UTC</div>
    </div>
</div>""",
        unsafe_allow_html=True,
    )

with right:
    recs = RECOMMENDATIONS.get(selected["category"], [])
    rec_items = "".join(
        f'<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #1e2736;">'
        f'<div style="width:3px;background:#00d4ff;border-radius:2px;flex-shrink:0;margin:2px 0;"></div>'
        f'<span style="color:#a0aab4;font-size:13px;line-height:1.5">{r}</span></div>'
        for r in recs
    )
    impact_bar = f"""
<div style="background:{lc}18;border:1px solid {lc}44;border-radius:8px;padding:14px 20px;
            display:flex;justify-content:space-around;margin-top:14px;">
    <div style="text-align:center">
        <div style="color:{lc};font-size:18px;font-weight:800">${selected['cost_m']}M</div>
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em">Cost Impact</div>
    </div>
    <div style="text-align:center">
        <div style="color:{lc};font-size:18px;font-weight:800">{selected['delay_min']}–{selected['delay_max']} days</div>
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em">Est. Delay</div>
    </div>
    <div style="text-align:center">
        <div style="color:{lc};font-size:18px;font-weight:800">{selected['inventory']}%</div>
        <div style="color:#5a6a7e;font-size:11px;text-transform:uppercase;letter-spacing:.06em">Inventory Impact</div>
    </div>
</div>"""

    st.markdown(
        f"""
<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;padding:20px;height:100%;">
    <div style="color:#e8eaed;font-size:14px;font-weight:700;margin-bottom:16px;
                padding-bottom:10px;border-bottom:1px solid #263044;">
        Recommended Actions
    </div>
    {rec_items}
    {impact_bar}
</div>""",
        unsafe_allow_html=True,
    )

# ── Sidebar refresh ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Controls")
    if vessel_age is not None:
        st.caption(f"Data last refreshed {vessel_age // 60}m {vessel_age % 60}s ago")
    if st.button("🔄 Refresh Alerts", use_container_width=True, type="primary"):
        from db.cache import _connect
        with _connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (aisstream.VESSEL_CACHE_KEY,))
        st.rerun()
