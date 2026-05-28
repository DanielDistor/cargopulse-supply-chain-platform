import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ────────────────────────────────────────────────────────────────
           SOURCE: josna-14/Maritime_Vessel_Tracking
           index.css  +  Dashboard.js inline styles
           All values copied verbatim — no approximations.
        ──────────────────────────────────────────────────────────────── */

        /* index.css :root / body */
        .stApp {
            background: #f4f7fa;
            font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            color: #0f1c2e;
        }
        header[data-testid="stHeader"] { display: none !important; }

        /* .app-container padding: 2rem + block-container override */
        .block-container {
            padding-top: 0 !important;
            padding-bottom: 1.25rem !important;
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
        }

        /* index.css .page { gap: 1.5rem }  ← exact */
        [data-testid="stVerticalBlock"] { gap: 1.5rem !important; }

        /* Dashboard.js main split gap: "25px"  ← exact */
        [data-testid="stHorizontalBlock"] { gap: 1.5625rem !important; }

        /* ── Hide sidebar ── */
        [data-testid="stSidebar"]       { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarContent"] { display: none !important; }

        /* Navbar.css .navbar__links a.active / a:hover
           background: rgba(255,255,255,0.2)  ← exact */
        .cp-nav-link:hover {
            background: rgba(255, 255, 255, 0.2) !important;
            color: #fff !important;
        }

        /* Plotly chart: Dashboard.js section style
           borderRadius: "12px", boxShadow: "0 2px 10px rgba(0,0,0,0.05)"  ← exact */
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
           Dashboard.js h1: color "#1f3c88" — inline overrides, use that */
        h1 { color: #1f3c88 !important; font-weight: 700; }
        h2, h3 { color: #333 !important; font-weight: 600; }

        .stCaption, [data-testid="stCaptionContainer"] p {
            color: #687590 !important;   /* index.css .card__label color */
            font-size: 0.85rem !important;
        }

        /* Buttons — reference Track button style */
        .stButton button {
            background: white;
            color: #1f3c88;
            border: 1px solid #1f3c88;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.8rem;
            transition: all 0.2s;
        }
        .stButton button:hover {
            background: #1f3c88;
            color: white;
        }

        /* Spinner */
        .stSpinner > div { border-top-color: #1f3c88 !important; }

        /* index.css .auth__message */
        [data-testid="stInfo"] {
            background-color: #e7f6ff !important;
            border: 1px solid #b4dcff !important;
            border-radius: 10px !important;
            color: #1565c0 !important;
        }

        [data-testid="stWarning"] {
            background-color: #fff8e1 !important;
            border: 1px solid #fde68a !important;
            border-radius: 10px !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid #eee !important;
            border-radius: 12px !important;
            background-color: white !important;
        }

        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background-color: white;
            border-color: #cbd5ef;
            border-radius: 10px;
        }

        /* index.css .filters input border: 1px solid #cbd5ef */
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: #e3f2fd !important;
            border: 1px solid #90caf9 !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span { color: #1565c0 !important; }

        /* progress bar: linear-gradient(90deg, #1e3c72, #2a5298) */
        [data-testid="stSlider"] [class*="thumb"] { background-color: #1e3c72 !important; }
        [data-testid="stSlider"] [class*="track"]  { background-color: #2a5298 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def navbar(current: str = "") -> None:
    """Navbar.css exact values:
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)
    padding: 1rem 2rem
    box-shadow: 0 4px 12px rgba(0,0,0,0.15)
    brand: 1.4rem / 700
    logo: 2rem
    links gap: 1.25rem
    link: color #fff, font-weight 500, padding 0.4rem 0.6rem, border-radius 6px
    active: background rgba(255,255,255,0.2)
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
        if label == current:
            links += (
                f'<a href="{path}" target="_self" style="'
                f'color:#fff;text-decoration:none;font-weight:500;'
                f'padding:0.4rem 0.6rem;border-radius:6px;'
                f'background:rgba(255,255,255,0.2);white-space:nowrap;">'
                f'{label}</a>'
            )
        else:
            links += (
                f'<a href="{path}" target="_self" class="cp-nav-link" style="'
                f'color:#fff;text-decoration:none;font-weight:500;'
                f'padding:0.4rem 0.6rem;border-radius:6px;'
                f'transition:background 0.2s ease;white-space:nowrap;">'
                f'{label}</a>'
            )

    # Navbar.css: padding 1rem 2rem, background gradient, box-shadow exact
    st.markdown(
        f"""
        <div style="
            width:100vw;position:relative;left:50%;transform:translateX(-50%);
            background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
            box-shadow:0 4px 12px rgba(0,0,0,0.15);
            padding:1rem 2rem;
            display:flex;align-items:center;justify-content:space-between;
            box-sizing:border-box;margin-bottom:1.25rem;
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
    """Dashboard.js header: h1 color #1f3c88 24px, p color #666 14px."""
    st.markdown(
        '<div style="margin-bottom:25px;">'
        f'<h1 style="margin:0 0 5px 0;color:#1f3c88;font-size:24px;font-weight:700">{title}</h1>'
        f'<p style="margin:0;color:#666;font-size:14px">{subtitle}</p>'
        '</div>',
        unsafe_allow_html=True,
    )
