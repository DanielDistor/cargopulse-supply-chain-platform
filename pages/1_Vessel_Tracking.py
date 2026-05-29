import json
import os
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from services import aisstream
from db import cache
from components.styles import inject_global_css, page_header, navbar

load_dotenv()

st.set_page_config(page_title="Vessel Tracking | CargoPulse", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="vessel_refresh")
inject_global_css()
navbar(current="Vessel Tracking")
page_header(
    "Live Vessel Tracking",
    "Real-time AIS positions near major ports · vessel types · risk zones",
)

PORTS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "ports.json")
with open(PORTS_PATH) as f:
    ports = json.load(f)

bounding_boxes = [aisstream.make_port_bounding_box(p["lat"], p["lon"]) for p in ports]

ANCHORED_STATUSES = {1, 5}
UNDERWAY_STATUSES = {0, 8}

RISK_ZONES = [
    {"name": "Gulf of Aden",     "lat": 12.5,  "lon":  47.5, "radius_km": 450, "type": "Piracy"},
    {"name": "Red Sea Corridor", "lat": 19.0,  "lon":  38.5, "radius_km": 480, "type": "Security"},
    {"name": "Hormuz Strait",    "lat": 26.6,  "lon":  56.3, "radius_km": 100, "type": "Geopolitical"},
    {"name": "Malacca Strait",   "lat":  3.0,  "lon": 101.5, "radius_km": 160, "type": "Congestion"},
    {"name": "South China Sea",  "lat": 13.5,  "lon": 113.0, "radius_km": 650, "type": "Congestion"},
    {"name": "Taiwan Strait",    "lat": 24.5,  "lon": 119.5, "radius_km": 110, "type": "Geopolitical"},
    {"name": "Suez Canal",       "lat": 30.4,  "lon":  32.4, "radius_km":  90, "type": "Congestion"},
    {"name": "Panama Canal",     "lat":  9.1,  "lon": -79.7, "radius_km":  75, "type": "Congestion"},
]


def classify_movement(row: dict) -> str:
    nav = row.get("status")
    spd = row.get("speed") or 0.0
    if nav in ANCHORED_STATUSES or (nav not in UNDERWAY_STATUSES and spd < 1.0):
        return "Anchored / Moored"
    if spd >= 5.0 or nav in UNDERWAY_STATUSES:
        return "Underway"
    return "Slow / Maneuvering"


def get_vessel_category(code=None, name: str = "", nav_status=None) -> str:
    """
    Classify vessel type.  Priority order:
      1. AIS navigational status 7 = 'Engaged in Fishing' (definitive)
      2. AIS ShipStaticData type code (definitive when available)
      3. Ship-name keyword heuristics (broad fallback)
    """
    # Nav status 7 is 'Engaged in fishing' — reliable even without static data
    if nav_status == 7:
        return "Fishing"

    if code is not None:
        try:
            c = int(code)
            if 70 <= c <= 79: return "Cargo"
            if 80 <= c <= 89: return "Tanker"
            if 60 <= c <= 69: return "Passenger"
            if c == 30:        return "Fishing"
            if 50 <= c <= 59: return "Special"
            # Additional AIS codes: towing (21-22, 31-32), dredging (33),
            # diving (34), military (35), law enforcement (55)
            if c in (21, 22, 31, 32, 33, 34, 35, 55): return "Special"
        except (ValueError, TypeError):
            pass

    nm = (name or "").upper()

    # ── Tanker — check before Cargo; some names contain both words ─────────
    _TANKER = [
        # vessel type keywords
        "TANKER", " OIL ", "CRUDE OIL", "CRUDE TK", "CRUDE CARRIER",
        "LNG ", " LNG", "LPG ", " LPG", "VLCC", "ULCC",
        "AFRAMAX", "SUEZMAX", "CHEMICAL", "PRODUCT TK", "PRODUCT CARRIER",
        "BITUMEN", "NAPHTHA", "ASPHALT", "ETHYLENE", "AMMONIA CARRIER",
        "PETROLEUM", "BUNKER", "SHUTTLE TK", "SHUTTLE TANKER",
        "FPSO", " FSO ", "ACID CARRIER",
        # "MT " prefix = Motor Tanker
        "MT EAGLE", "MT FALCON", "MT CONDOR",
        # operators / fleets
        "TEEKAY", "FRONTLINE", "TSAKOS", "EURONAV", "DHT ",
        "HAFNIA", "ARDMORE", "DIAMOND S", "GENER8", "MINERVA",
        "NORDIC CHEMICAL", "NORDIC TANKER", "NORDIC TK",
        "SCORPIO TK", "NAVIGATOR GAS", "NAVIGATOR ", "EXMAR",
        "STENA BULK", "BW GAS", "BW EPIC", "BW EAGLE",
        "DELTA TK", "GULF TK", "COSMO OIL", "VELA ", "NITC",
        "INTERNATIONAL SEAWAYS", "FLEX LNG", "MOL CHEMICAL",
        "AET TANKER", " AET ", "MARANGAS", "GEOGAS",
        "DORADO", "OLYMPIC SHIPPING", "OLYMPIC TK",
        "SVITZER OIL", "PETROBRAS", "SOCAR",
    ]
    if any(k in nm for k in _TANKER): return "Tanker"

    # ── Cargo: container, bulk, general cargo, RoRo, car carriers ──────────
    _CARGO = [
        # vessel type keywords
        "CONTAINER", "CARGO", "BULK", "BULKER", "FREIGHTER", "CARRIER",
        "RORO", "RO RO", "RO-RO", "ROPAX", "CAR CARRIER", "PCC ",
        "VEHICLE CARRIER", "AUTO CARRIER", "PCL ", "PCTC",
        "ULTRAMAX", "SUPRAMAX", "HANDYSIZE", "HANDYMAX", "CAPESIZE",
        "KAMSARMAX", "NEWCASTLEMAX", "PANAMAX",
        # commodity keywords
        " ORE ", " COAL ", "GRAIN ", "CEMENT", "STONE ",
        "STEEL ", " IRON ", " WOOD ", "LUMBER", "TIMBER",
        # major container lines
        "MAERSK", "MSC ", " MSC", "CMA CGM", "HAPAG",
        "EVERGREEN", "EVER ", "YANG MING", " ONE ", "OOCL",
        " APL ", " NYK ", " MOL ", "K LINE", "PIL ",
        "ZIM ", "HMM ", "WAN HAN", "SITC ", "T.S. LINE",
        "SM LINE", "GOLD STAR LINE", "RCL ", "KMTC ",
        "ANTONG", "SINOLINES", "COSCO ",
        # bulk / general cargo operators
        "SEASPAN", "COSTAMARE", "DANAOS", "DIANA SHIPPING",
        "STAR BULK", "GOLDEN OCEAN", "NAVIOS", "PACIFIC BASIN",
        "EAGLE BULK", "GRINDROD", "OLDENDORFF", "SWIRE ",
        "SCORPIO BULK", "BERGE ", "VALE ", "GREAT WALL",
        "ATLAS BULK", "GLOBUS ", "GENCO ", "SAFE BULKERS",
        # RoRo / car carrier operators
        "GLOVIS", "EUKOR", "WILHELMSEN", "WALLENIUS", "HOEGH",
        "HÖEGH", "K-LINE CAR", "NYK CAR", "MOL ACE",
        "ATLANTIC RORO", "LIBERTY ", "LODESTAR",
    ]
    if any(k in nm for k in _CARGO): return "Cargo"

    # ── Passenger ─────────────────────────────────────────────────────────
    _PASS = [
        # generic
        "FERRY", "PASSENGER", "CRUISE", "LINER", "ROPAX",
        # cruise lines
        "CELEBRITY", "CARNIVAL", "ROYAL CARIBBEAN", "COSTA ",
        "PRINCESS", "QUEEN ", "EMPRESS", "VIKING ",
        "PONANT", "SILVERSEA", "SEABOURN", "AZAMARA",
        "CUNARD", "OCEANIA", "REGENT ", "WINDSTAR",
        "NORWEGIAN CRUISE", " NCL ", "HURTIGRUTEN",
        "AURORA ", "DREAM ", "MARELLA",
        "SWAN HELLENIC", "SAGA CRUISES", "SCENIC ",
        # ferry operators / routes
        "DFDS", "COLOR LINE", "FJORDLINE", "STENA LINE",
        " FJORD", "IRISH FERRIES", "BRITTANY", "P&O FERRY",
        "WASA ", "TALLINK", "SILJA", "VIKING LINE",
        "CORSICA", "LA MERIDIONALE", "TTT LINE",
    ]
    if any(k in nm for k in _PASS): return "Passenger"

    # ── Fishing ────────────────────────────────────────────────────────────
    _FISH = [
        "FISH", "TRAWL", "PURSE", "SEINER", "LONGLINER",
        "FISHERMAN", "SQUID", "CATCHER", "ANGLER",
        "HERRING", "TUNA ", "MACKEREL",
    ]
    if any(k in nm for k in _FISH): return "Fishing"

    # ── Special / service vessels ──────────────────────────────────────────
    _SPEC = [
        # tug / workboat
        "TUG ", " TUG", "TUGBOAT", "SVITZER", "KOTUG", "SMIT ",
        # pilot / port
        "PILOT", "PORT ", " PORT", "HARBOUR", "HARBOR",
        # dredging
        "DREDG", "CUTTER SUCTION", "TRAILING SUCTION", "HOPPER",
        # offshore / supply
        "OFFSHORE", " PSV", " AHTS", "ANCHOR HANDLING",
        "SUPPLY VESSEL", " CSV", "MULTI PURPOSE VESSEL",
        "DIVE SUPPORT", "ROV SUPPORT", "PLATFORM SUPPLY",
        # cable / survey / research
        "CABLE ", "CABLE SHIP", "CABLE LAYER",
        "SURVEY", "RESEARCH", "OCEANOGRAPH",
        "BUOY TENDER", "LIGHTHOUSE",
        # crane / heavy lift
        "CRANE VESSEL", "HEAVY LIFT", "THIALF", "SLEIPNIR",
        # emergency / safety
        "ICEBREAKER", "ICE BREAKER", "RESCUE", "FIREBOAAT", "FIREBOAT",
        "COASTGUARD", "COAST GUARD", "SAR ", "PATROL",
        # military
        "NAVAL", "WARSHIP", "HMS ", "USS ", "USCGC",
        # platform / barge
        "PLATFORM", " BARGE", "PONTOON", "FPSO",
        # other service
        "WATER BOAT", "BUNKER BARGE", "OIL SPILL",
    ]
    if any(k in nm for k in _SPEC): return "Special"

    return "Other"


# ── Refresh button + fetch ─────────────────────────────────────────────
col_info, col_btn = st.columns([5, 1])
with col_btn:
    if st.button("⟳ Refresh", type="primary", use_container_width=True):
        from db.cache import _connect
        with _connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (aisstream.VESSEL_CACHE_KEY,))
        st.rerun()

with st.spinner("Fetching live vessel positions..."):
    vessels = aisstream.get_vessels(bounding_boxes)

age = cache.get_age_seconds(aisstream.VESSEL_CACHE_KEY)
with col_info:
    if age is not None:
        st.caption(f"🕐 Last updated {age // 60}m {age % 60}s ago · **{len(vessels)} vessels** tracked")
    else:
        st.caption("No cached data yet — fetching now…")

if not vessels:
    st.warning("No vessel data available. Check that AISSTREAM_API_KEY is set and try refreshing.")
    st.stop()

# ── Build dataframe ────────────────────────────────────────────────────
df = pd.DataFrame(vessels)
if not df.empty and {"lat", "lon"}.issubset(df.columns):
    df = df.dropna(subset=["lat", "lon"])
else:
    df = df.reindex(columns=["lat", "lon", "mmsi", "name", "speed", "heading", "status"])

df["movement"] = df.apply(classify_movement, axis=1)
df["category"] = df.apply(
    lambda r: get_vessel_category(
        r.get("vessel_type_code"),
        r.get("name", ""),
        r.get("status"),
    ),
    axis=1,
)

total    = len(df)
underway = int((df["movement"] == "Underway").sum())
slow     = int((df["movement"] == "Slow / Maneuvering").sum())
anchored = int((df["movement"] == "Anchored / Moored").sum())

# ── Fleet stat cards (dark) ─────────────────────────────────────────────
def fleet_card(label: str, value: int, pct: float, dot_color: str) -> str:
    dot = (
        f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
        f'background:{dot_color};margin-right:6px;vertical-align:middle;flex-shrink:0"></span>'
    )
    return (
        f'<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;'
        f'padding:16px 18px;height:96px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="display:flex;align-items:center;color:#6b7fa3;font-size:11px;'
        f'text-transform:uppercase;letter-spacing:.07em">{dot}{label}</div>'
        f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{value}</div>'
        f'<div style="color:{dot_color};font-size:12px">{pct:.0f}% of fleet</div>'
        f'</div>'
    )

s1, s2, s3, s4 = st.columns(4)
s1.markdown(
    f'<div style="background:#1a1f2e;border:1px solid #263044;border-radius:10px;'
    f'padding:16px 18px;height:96px;display:flex;flex-direction:column;justify-content:space-between;">'
    f'<div style="color:#6b7fa3;font-size:11px;text-transform:uppercase;letter-spacing:.07em">Total Vessels</div>'
    f'<div style="color:#e8eaed;font-size:26px;font-weight:800;line-height:1">{total}</div>'
    f'<div style="color:#6b7fa3;font-size:12px">tracked right now</div>'
    f'</div>',
    unsafe_allow_html=True,
)
s2.markdown(fleet_card("Underway",           underway, underway / total * 100 if total else 0, "#4caf50"), unsafe_allow_html=True)
s3.markdown(fleet_card("Slow / Maneuvering", slow,     slow / total * 100     if total else 0, "#ffb74d"), unsafe_allow_html=True)
s4.markdown(fleet_card("Anchored / Moored",  anchored, anchored / total * 100 if total else 0, "#ef5350"), unsafe_allow_html=True)

st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

# ── Prepare map data ────────────────────────────────────────────────────
def _safe_float(v):
    try:
        f = float(v)
        return None if f != f else round(f, 2)   # NaN → None
    except (TypeError, ValueError):
        return None

def _safe_int(v):
    try:
        i = int(float(v))
        return None if i == 511 else i   # 511 = heading not available in AIS
    except (TypeError, ValueError):
        return None

vessels_for_map = [
    {
        "lat":      float(row["lat"]),
        "lon":      float(row["lon"]),
        "name":     str(row.get("name") or "Unknown"),
        "mmsi":     str(row.get("mmsi") or ""),
        "speed":    _safe_float(row.get("speed")),
        "heading":  _safe_int(row.get("heading")),
        "category": str(row["category"]),
        "movement": str(row["movement"]),
    }
    for _, row in df.iterrows()
]

ports_for_map = [{"name": p["name"], "lat": p["lat"], "lon": p["lon"]} for p in ports]

MAP_H = 640

# ── Data injection (f-string, isolated from JS template) ───────────────
_DATA_JS = (
    f"const VESSELS = {json.dumps(vessels_for_map)};\n"
    f"const PORTS_DATA = {json.dumps(ports_for_map)};\n"
)

# ── HTML template (no f-string — avoids JS {{ }} escaping) ─────────────
_HTML_HEAD = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box;}
html,body{width:100%;height:100%;overflow:hidden;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
#map{width:100%;height:100%;}

/* ── Status bar ── */
#status-bar{
  position:absolute;top:14px;left:50%;transform:translateX(-50%);
  background:rgba(15,23,42,0.88);color:#f1f5f9;
  border-radius:22px;padding:7px 20px;
  font-size:12px;font-weight:600;letter-spacing:.02em;
  display:flex;align-items:center;gap:14px;
  z-index:1000;backdrop-filter:blur(6px);
  box-shadow:0 2px 10px rgba(0,0,0,0.25);white-space:nowrap;
}
.sdot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:middle;}

/* ── Filter panel ── */
#filter-panel{
  position:absolute;top:14px;right:14px;
  background:white;border-radius:10px;padding:12px 14px;
  box-shadow:0 2px 12px rgba(0,0,0,0.13);z-index:1000;min-width:172px;
}
.fp-hdr{font-size:11px;font-weight:700;color:#1e293b;
  display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;}
.live-pill{background:#22c55e;color:white;font-size:9px;font-weight:700;
  border-radius:4px;padding:2px 6px;letter-spacing:.05em;}
#fleet-select{
  width:100%;padding:5px 8px;border:1px solid #e2e8f0;border-radius:6px;
  font-size:12px;color:#334155;cursor:pointer;margin-bottom:9px;
}
/* ── Legend ── */
#legend{
  position:absolute;bottom:28px;right:14px;
  background:white;border-radius:10px;padding:12px 14px;
  box-shadow:0 2px 12px rgba(0,0,0,0.13);z-index:1000;min-width:160px;
}
.lg-hdr{font-size:12px;font-weight:700;color:#1e293b;margin-bottom:9px;}
.lg-row{display:flex;align-items:center;gap:9px;margin-bottom:6px;}
.lg-row:last-child{margin-bottom:0;}
.lg-lbl{font-size:11px;color:#475569;}

/* ── Popup ── */
.leaflet-popup-content-wrapper{
  border-radius:10px!important;
  box-shadow:0 4px 20px rgba(0,0,0,0.14)!important;
  padding:0!important;
}
.leaflet-popup-content{margin:0!important;}
.leaflet-popup-tip-container{display:none!important;}
.pu{padding:12px 14px;min-width:175px;}
.pu-name{font-size:13px;font-weight:700;color:#1e293b;margin-bottom:7px;}
.pu-row{display:flex;justify-content:space-between;font-size:11px;
  color:#64748b;margin-bottom:3px;}
.pu-val{color:#334155;font-weight:600;}
.pu-badge{display:inline-block;padding:2px 7px;border-radius:4px;
  font-size:10px;font-weight:700;margin-top:5px;}
</style>
</head>
<body>
<div id="map"></div>

<div id="status-bar">
  <span><span class="sdot" style="background:#22c55e;"></span><b id="cnt-active">0</b> Active</span>
</div>

<div id="filter-panel">
  <div class="fp-hdr">Filters <span class="live-pill">● LIVE</span></div>
  <select id="fleet-select" onchange="applyFilter()">
    <option value="all">Show All Fleets</option>
    <option value="Cargo">Cargo</option>
    <option value="Tanker">Tanker</option>
    <option value="Passenger">Passenger</option>
    <option value="Fishing">Fishing</option>
    <option value="Special">Special</option>
    <option value="Other">Other</option>
  </select>
</div>

<div id="legend">
  <div class="lg-hdr">Vessel Types</div>
</div>

<script>
"""

_SCRIPT = """\

// ── Map init ─────────────────────────────────────────────────────────────
const map = L.map('map', {zoomControl: true}).setView([30, 20], 3);

L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 19,
}).addTo(map);

// ── Vessel styles ─────────────────────────────────────────────────────────
const VSTYLE = {
  Cargo:     {color: '#22c55e', shape: 'triangle',  label: 'Cargo (Green)'},
  Tanker:    {color: '#ef4444', shape: 'diamond',   label: 'Tanker (Red)'},
  Passenger: {color: '#3b82f6', shape: 'circle',    label: 'Passenger (Blue)'},
  Fishing:   {color: '#f97316', shape: 'square',    label: 'Fishing (Orange)'},
  Special:   {color: '#a855f7', shape: 'star',      label: 'Special (Purple)'},
  Other:     {color: '#334155', shape: 'triangle',  label: 'Other (Gray)'},
};

const _SHADOW = 'filter="drop-shadow(0 1px 3px rgba(0,0,0,0.55))"';

function svgIcon(shape, color, sz) {
  sz = sz || 20;
  const h  = (sz / 2).toFixed(2);
  const e  = (sz - 1).toFixed(2);
  const sh = sz <= 14 ? '' : _SHADOW;   // skip shadow on tiny legend icons
  if (shape === 'triangle')
    return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" ${sh}>` +
      `<polygon points="${h},1.5 ${e},${e} 1.5,${e}" fill="${color}" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>`;
  if (shape === 'diamond')
    return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" ${sh}>` +
      `<polygon points="${h},1.5 ${e},${h} ${h},${e} 1.5,${h}" fill="${color}" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>`;
  if (shape === 'circle')
    return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" ${sh}>` +
      `<circle cx="${h}" cy="${h}" r="${(sz/2 - 1.5).toFixed(2)}" fill="${color}" stroke="white" stroke-width="2"/></svg>`;
  if (shape === 'square')
    return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" ${sh}>` +
      `<rect x="2" y="2" width="${sz - 4}" height="${sz - 4}" rx="2.5" fill="${color}" stroke="white" stroke-width="2"/></svg>`;
  if (shape === 'star') {
    const pts = [];
    const cx = sz / 2, cy = sz / 2, ro = sz / 2 - 2, ri = ro * 0.42;
    for (let i = 0; i < 10; i++) {
      const ang = (i * Math.PI / 5) - Math.PI / 2;
      const r = i % 2 === 0 ? ro : ri;
      pts.push(`${(cx + r * Math.cos(ang)).toFixed(2)},${(cy + r * Math.sin(ang)).toFixed(2)}`);
    }
    return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" ${sh}>` +
      `<polygon points="${pts.join(' ')}" fill="${color}" stroke="white" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }
  return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}" ${sh}>` +
    `<circle cx="${h}" cy="${h}" r="${(sz/2 - 1.5).toFixed(2)}" fill="${color}" stroke="white" stroke-width="2"/></svg>`;
}

function makeIcon(category) {
  const s = VSTYLE[category] || VSTYLE.Other;
  return L.divIcon({
    html: svgIcon(s.shape, s.color, 20),
    className: '',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -12],
  });
}

// ── Movement badge ────────────────────────────────────────────────────────
const MOV_COLOR = {'Underway': '#22c55e', 'Slow / Maneuvering': '#f59e0b', 'Anchored / Moored': '#ef4444'};
function movBadge(mv) {
  const c = MOV_COLOR[mv] || '#64748b';
  return `<span class="pu-badge" style="background:${c}18;color:${c};">${mv}</span>`;
}

// ── Popup HTML ─────────────────────────────────────────────────────────────
function popupHtml(v) {
  const spd = v.speed  != null ? v.speed + ' kn' : 'N/A';
  const hdg = v.heading != null ? v.heading + '°' : 'N/A';
  return `<div class="pu">
    <div class="pu-name">${v.name || 'Unknown'}</div>
    <div class="pu-row"><span>MMSI</span><span class="pu-val">${v.mmsi}</span></div>
    <div class="pu-row"><span>Type</span><span class="pu-val">${v.category}</span></div>
    <div class="pu-row"><span>Speed</span><span class="pu-val">${spd}</span></div>
    <div class="pu-row"><span>Heading</span><span class="pu-val">${hdg}</span></div>
    ${movBadge(v.movement)}
  </div>`;
}

// ── Add vessel markers ─────────────────────────────────────────────────────
const vesselLayer = L.layerGroup().addTo(map);
const allMarkers = VESSELS.map(function(v) {
  const m = L.marker([v.lat, v.lon], {icon: makeIcon(v.category)})
    .bindPopup(popupHtml(v), {maxWidth: 220});
  return {m, cat: v.category, lat: v.lat, lon: v.lon};
});
allMarkers.forEach(function(o) { vesselLayer.addLayer(o.m); });

// ── Update status bar ─────────────────────────────────────────────────────
function updateCounts(filter) {
  let active = 0;
  allMarkers.forEach(function(o) {
    if (filter === 'all' || o.cat === filter) active++;
  });
  document.getElementById('cnt-active').textContent = active;
}

// ── Filter ────────────────────────────────────────────────────────────────
function applyFilter() {
  const f = document.getElementById('fleet-select').value;
  vesselLayer.clearLayers();
  allMarkers.forEach(function(o) {
    if (f === 'all' || o.cat === f) vesselLayer.addLayer(o.m);
  });
  updateCounts(f);
}

// ── Legend ────────────────────────────────────────────────────────────────
const legendEl = document.getElementById('legend');
Object.entries(VSTYLE).forEach(function([cat, s]) {
  const row = document.createElement('div');
  row.className = 'lg-row';
  row.innerHTML = svgIcon(s.shape, s.color, 13) + `<span class="lg-lbl">${s.label}</span>`;
  legendEl.appendChild(row);
});

// ── Init ──────────────────────────────────────────────────────────────────
updateCounts('all');
</script>
</body>
</html>
"""

map_html = _HTML_HEAD + _DATA_JS + _SCRIPT
components.html(map_html, height=MAP_H, scrolling=False)

st.divider()

# ── Vessel table ────────────────────────────────────────────────────────
st.markdown(
    '<div style="color:#1e293b;font-size:15px;font-weight:700;margin-bottom:8px;">All Vessels</div>',
    unsafe_allow_html=True,
)
display_df = df[["name", "category", "movement", "speed", "heading"]].copy()
display_df.columns = ["Vessel", "Type", "Status", "Speed (kn)", "Heading"]
st.dataframe(
    display_df.sort_values("Speed (kn)", ascending=False),
    use_container_width=True,
    height=320,
    hide_index=True,
)
