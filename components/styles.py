import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ─────────────────────────────────────────────────────────────────
           SOURCE TOKENS: josna-14/Maritime_Vessel_Tracking
           index.css + Navbar.css + Dashboard.js inline styles
        ───────────────────────────────────────────────────────────────── */

        /* index.css :root / body — exact */
        .stApp {
            background: #f4f7fa;
            font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            color: #0f1c2e;
        }
        header[data-testid="stHeader"] { display: none !important; }

        /* .app-container { padding: 2rem clamp(1rem, 5vw, 3rem) }
           We use 1.25rem sides to match the tighter end of clamp.
           Top: 0 (navbar provides its own margin-bottom). */
        .block-container {
            padding-top: 0 !important;
            padding-bottom: 1.25rem !important;
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
            max-width: 100% !important;
        }

        /* ── CRITICAL: gap must be 0 so HTML margin-bottom is the
           sole spacing authority — matching reference exactly.
           Reference: .page { gap: 1.5rem } — but Dashboard.js ALSO
           sets marginBottom:"25px" on each section. In flex, those
           add: 24px gap + 25px margin = 49px. We eliminate the gap
           so only the 25px HTML margin applies. ── */
        [data-testid="stVerticalBlock"] { gap: 0 !important; }

        /* Remove Streamlit element wrapper spacing */
        [data-testid="element-container"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }

        /* Dashboard.js main split: gap "25px" = 1.5625rem — exact */
        [data-testid="stHorizontalBlock"] { gap: 1.5625rem !important; }

        /* Hide sidebar */
        [data-testid="stSidebar"]       { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarContent"] { display: none !important; }

        /* Navbar.css .navbar__links a.active / a:hover
           background: rgba(255,255,255,0.2) — exact */
        .cp-nav-link:hover {
            background: rgba(255, 255, 255, 0.2) !important;
        }

        /* Map panel: paper_bgcolor="#0f2340" fills the chart area.
           The CSS background shows only in the 44px title strip at top.
           Dashboard.js section: borderRadius "12px", shadow exact. */
        [data-testid="stPlotlyChart"] {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }

        /* Dataframes */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }

        hr { border-color: #eee !important; margin: 1.5rem 0; }

        /* index.css .page__header h1: color #0f1c2e
           Dashboard.js h1 inline: color "#1f3c88" — inline wins */
        h1 { color: #1f3c88 !important; font-weight: 700; }
        h2, h3 { color: #333 !important; font-weight: 600; }

        /* index.css .card__label: color #687590 */
        .stCaption, [data-testid="stCaptionContainer"] p {
            color: #687590 !important;
            font-size: 0.85rem !important;
        }

        /* Spinner */
        .stSpinner > div { border-top-color: #1f3c88 !important; }

        /* Selectbox */
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background-color: white;
            border-color: #cbd5ef;
            border-radius: 10px;
        }

        /* index.css progress: linear-gradient(90deg, #1e3c72, #2a5298) */
        [data-testid="stSlider"] [class*="thumb"] { background-color: #1e3c72 !important; }
        [data-testid="stSlider"] [class*="track"]  { background-color: #2a5298 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def navbar(current: str = "") -> None:
    """
    Navbar.css exact values:
      background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)
      padding: 1rem 2rem
      box-shadow: 0 4px 12px rgba(0,0,0,0.15)
      brand: 1.4rem / 700, logo: 2rem
      links gap: 1.25rem
      link: color #fff, font-weight 500, padding 0.4rem 0.6rem, border-radius 6px
      active: background rgba(255,255,255,0.2)
    margin-bottom matches .page gap (1.5rem) so first section starts correctly.
    """
    _pages = [
        ("Dashboard",        "/"),
        ("Vessel Tracking",  "/Vessel_Tracking"),
        ("Port Congestion",  "/Port_Congestion"),
        ("Delay Forecast",   "/Delay_Forecast"),
        ("Supplier Risk",    "/Supplier_Risk"),
        ("Risk Alerts",      "/Risk_Alerts"),
    ]

    links = ""
    for label, path in _pages:
        active = label == current
        bg = "background:rgba(255,255,255,0.2);" if active else ""
        links += (
            f'<a href="{path}" target="_self" class="{"" if active else "cp-nav-link"}" style="'
            f'color:#fff;text-decoration:none;font-weight:500;'
            f'padding:0.4rem 0.6rem;border-radius:6px;{bg}white-space:nowrap;">'
            f'{label}</a>'
        )

    st.markdown(
        f"""
        <div style="
            width:100vw;position:relative;left:50%;transform:translateX(-50%);
            background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
            box-shadow:0 4px 12px rgba(0,0,0,0.15);
            padding:1rem 2rem;
            display:flex;align-items:center;justify-content:space-between;
            box-sizing:border-box;
            margin-bottom:1.5rem;
        ">
            <div style="display:flex;align-items:center;gap:0.5rem;flex-shrink:0;">
                <span style="font-size:2rem">⚓</span>
                <span style="color:#fff;font-size:1.4rem;font-weight:700;">CargoPulse</span>
            </div>
            <div style="display:flex;align-items:center;gap:1.25rem;">{links}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    """Dashboard.js: h1 #1f3c88/24px, p #666/14px, marginBottom 25px."""
    st.markdown(
        '<div style="margin:0 0 25px 0;">'
        f'<h1 style="margin:0 0 5px 0;color:#1f3c88;font-size:24px;font-weight:700">{title}</h1>'
        f'<p style="margin:0;color:#666;font-size:14px">{subtitle}</p>'
        '</div>',
        unsafe_allow_html=True,
    )
