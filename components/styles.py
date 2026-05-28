import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Page chrome ── */
        .stApp { background-color: #f1f5f9; }
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0.25rem !important; padding-bottom: 1rem !important; }

        /* ── Tighten element spacing globally ── */
        [data-testid="stVerticalBlock"] { gap: 0.6rem !important; }
        [data-testid="stHorizontalBlock"] { gap: 0.75rem !important; }

        /* ── Hide sidebar and its toggle button entirely ── */
        [data-testid="stSidebar"]       { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarContent"] { display: none !important; }

        /* ── Custom navbar link hover ── */
        .cp-nav-link:hover {
            color: #ffffff !important;
            background: rgba(255,255,255,0.12) !important;
        }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
        [data-testid="stSidebar"] .stMarkdown p { color: #64748b; }

        /* ── KPI metric cards ── */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        [data-testid="stMetricLabel"] { color: #64748b !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.08em; }
        [data-testid="stMetricValue"] { color: #1e293b !important; font-size: 28px !important; font-weight: 700 !important; }
        [data-testid="stMetricDelta"] svg { display: none; }

        /* ── Plotly chart containers ── */
        /* Border/radius handled at the column level for the map card via Home.py injection */
        [data-testid="stPlotlyChart"] {
            overflow: hidden;
        }

        /* ── Dataframes ── */
        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }

        /* ── Dividers ── */
        hr { border-color: #e2e8f0 !important; margin: 1.5rem 0; }

        /* ── Page title ── */
        h1 { color: #1e293b !important; font-weight: 800; letter-spacing: -0.02em; }
        h2 { color: #334155 !important; font-weight: 700; }
        h3 { color: #475569 !important; font-weight: 600; }

        /* ── Caption ── */
        .stCaption, [data-testid="stCaptionContainer"] p {
            color: #94a3b8 !important;
            font-size: 13px !important;
        }

        /* ── Buttons ── */
        .stButton button {
            background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-weight: 700;
            letter-spacing: 0.02em;
            transition: all 0.2s ease;
        }
        .stButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.3);
        }

        /* ── Info boxes ── */
        [data-testid="stInfo"] {
            background-color: #eff6ff !important;
            border: 1px solid #3b82f6 !important;
            border-radius: 10px !important;
            color: #1d4ed8 !important;
        }

        /* ── Warning boxes ── */
        [data-testid="stWarning"] {
            background-color: #fffbeb !important;
            border: 1px solid #f59e0b !important;
            border-radius: 10px !important;
        }

        /* ── Spinner ── */
        .stSpinner > div { border-top-color: #3b82f6 !important; }

        /* ── Expander ── */
        [data-testid="stExpander"] {
            border: 1px solid #e2e8f0 !important;
            border-radius: 10px !important;
            background-color: #ffffff !important;
        }

        /* ── Selectbox / Multiselect ── */
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background-color: #ffffff;
            border-color: #e2e8f0;
            border-radius: 8px;
        }

        /* ── Multiselect selected pills ── */
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: #f1f5f9 !important;
            border: 1px solid #cbd5e1 !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #475569 !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] [role="button"] {
            color: #64748b !important;
        }

        /* ── Slider ── */
        [data-testid="stSlider"] [class*="thumb"] { background-color: #3b82f6 !important; }
        [data-testid="stSlider"] [class*="track"] { background-color: #3b82f6 !important; }
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
                f'background:#3b82f6;color:#ffffff;'
                f'padding:6px 14px;border-radius:6px;'
                f'font-size:13px;font-weight:700;'
                f'text-decoration:none;white-space:nowrap;">'
                f'{label}</a>'
            )
        else:
            links += (
                f'<a href="{path}" target="_self" class="cp-nav-link" style="'
                f'color:#94a3b8;padding:6px 10px;border-radius:6px;'
                f'font-size:13px;font-weight:500;'
                f'text-decoration:none;white-space:nowrap;">'
                f'{label}</a>'
            )

    st.markdown(
        f"""
        <div style="
            width:100vw;position:relative;left:50%;transform:translateX(-50%);
            background:#1e3a5f;border-bottom:1px solid #1a3356;
            padding:0 2rem;height:54px;
            display:flex;align-items:center;justify-content:space-between;
            box-sizing:border-box;margin-bottom:1.5rem;
        ">
            <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
                <span style="font-size:22px">⚓</span>
                <span style="color:#ffffff;font-size:17px;font-weight:800;
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
            <h1 style="margin:0;padding:0;color:#1e293b;font-size:2rem;font-weight:800;">{title}</h1>
            <p style="margin:4px 0 0 0;color:#64748b;font-size:14px;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
