import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Page chrome ── */
        .stApp { background-color: #0f1117; }
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0.25rem !important; padding-bottom: 1rem !important; }

        /* ── Section spacing — matches reference 20-25px gaps ── */
        [data-testid="stVerticalBlock"] { gap: 1.5rem !important; }
        [data-testid="stHorizontalBlock"] { gap: 1.5rem !important; }

        /* ── Hide sidebar and its toggle button entirely ── */
        [data-testid="stSidebar"]       { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarContent"] { display: none !important; }

        /* ── Custom navbar link hover ── */
        .cp-nav-link:hover {
            color: #e8eaed !important;
            background: rgba(255,255,255,0.07) !important;
        }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background-color: #1a1f2e;
            border-right: 1px solid #1e2736;
        }
        [data-testid="stSidebar"] .stMarkdown p { color: #a0aab4; }

        /* ── KPI metric cards ── */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #1a1f2e 0%, #16202f 100%);
            border: 1px solid #263044;
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        }
        [data-testid="stMetricLabel"] { color: #6b7fa3 !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.08em; }
        [data-testid="stMetricValue"] { color: #e8eaed !important; font-size: 28px !important; font-weight: 700 !important; }
        [data-testid="stMetricDelta"] svg { display: none; }

        /* ── Plotly chart containers ── */
        [data-testid="stPlotlyChart"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #1e2736;
        }

        /* ── Dataframes ── */
        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #1e2736;
        }

        /* ── Dividers ── */
        hr { border-color: #1e2736 !important; margin: 1.5rem 0; }

        /* ── Page title ── */
        h1 { color: #e8eaed !important; font-weight: 800; letter-spacing: -0.02em; }
        h2 { color: #c9d1da !important; font-weight: 700; }
        h3 { color: #a0aab4 !important; font-weight: 600; }

        /* ── Caption ── */
        .stCaption, [data-testid="stCaptionContainer"] p {
            color: #5a6a7e !important;
            font-size: 13px !important;
        }

        /* ── Buttons ── */
        .stButton button {
            background: linear-gradient(135deg, #0099cc 0%, #00d4ff 100%);
            color: #0f1117;
            border: none;
            border-radius: 8px;
            font-weight: 700;
            letter-spacing: 0.02em;
            transition: all 0.2s ease;
        }
        .stButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(0, 212, 255, 0.3);
        }

        /* ── Info boxes ── */
        [data-testid="stInfo"] {
            background-color: #0d2035 !important;
            border: 1px solid #0099cc !important;
            border-radius: 10px !important;
            color: #a0cfea !important;
        }

        /* ── Warning boxes ── */
        [data-testid="stWarning"] {
            background-color: #1e1500 !important;
            border: 1px solid #b8860b !important;
            border-radius: 10px !important;
        }

        /* ── Spinner ── */
        .stSpinner > div { border-top-color: #00d4ff !important; }

        /* ── Expander ── */
        [data-testid="stExpander"] {
            border: 1px solid #1e2736 !important;
            border-radius: 10px !important;
            background-color: #1a1f2e !important;
        }

        /* ── Selectbox / Multiselect ── */
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background-color: #1a1f2e;
            border-color: #263044;
            border-radius: 8px;
        }

        /* ── Multiselect selected pills ── */
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: #1e2736 !important;
            border: 1px solid #374357 !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #a0aab4 !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] [role="button"] {
            color: #6b7fa3 !important;
        }

        /* ── Slider ── */
        [data-testid="stSlider"] [class*="thumb"] { background-color: #00d4ff !important; }
        [data-testid="stSlider"] [class*="track"] { background-color: #00d4ff !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def navbar(current: str = "") -> None:
    """Full-width dark navigation bar. Pass current= the label of the active page."""
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
                f'background:#00d4ff;color:#0f1117;'
                f'padding:6px 14px;border-radius:6px;'
                f'font-size:13px;font-weight:700;'
                f'text-decoration:none;white-space:nowrap;">'
                f'{label}</a>'
            )
        else:
            links += (
                f'<a href="{path}" target="_self" class="cp-nav-link" style="'
                f'color:#8899a6;padding:6px 10px;border-radius:6px;'
                f'font-size:13px;font-weight:500;'
                f'text-decoration:none;white-space:nowrap;">'
                f'{label}</a>'
            )

    st.markdown(
        f"""
        <div style="
            width:100vw;position:relative;left:50%;transform:translateX(-50%);
            background:#0d1822;border-bottom:1px solid #1e2736;
            padding:0 2rem;height:54px;
            display:flex;align-items:center;justify-content:space-between;
            box-sizing:border-box;margin-bottom:1.5rem;
        ">
            <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
                <span style="font-size:22px">⚓</span>
                <span style="color:#e8eaed;font-size:17px;font-weight:800;
                             letter-spacing:-0.01em;">CargoPulse</span>
            </div>
            <div style="display:flex;align-items:center;gap:4px;">{links}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    """Render a styled page header."""
    st.markdown(
        f"""
        <div style="margin-bottom:8px;">
            <h1 style="margin:0;padding:0;color:#e8eaed;font-size:2rem;font-weight:800;">{title}</h1>
            <p style="margin:4px 0 0 0;color:#5a6a7e;font-size:14px;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
