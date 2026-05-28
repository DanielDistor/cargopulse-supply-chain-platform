import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Page background ── */
        .stApp { background-color: #f3f4f6; }
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0.25rem !important; padding-bottom: 1rem !important; }

        /* ── Section spacing ── */
        [data-testid="stVerticalBlock"] { gap: 1.25rem !important; }
        [data-testid="stHorizontalBlock"] { gap: 1.25rem !important; }

        /* ── Hide sidebar ── */
        [data-testid="stSidebar"]       { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarContent"] { display: none !important; }

        /* ── Navbar link hover ── */
        .cp-nav-link:hover {
            color: #ffffff !important;
            background: rgba(255,255,255,0.12) !important;
        }

        /* ── Plotly chart panel ── */
        [data-testid="stPlotlyChart"] {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            background: #ffffff;
        }

        /* ── Dataframes ── */
        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }

        /* ── Dividers ── */
        hr { border-color: #e5e7eb !important; margin: 1.5rem 0; }

        /* ── Page titles ── */
        h1 { color: #111827 !important; font-weight: 800; letter-spacing: -0.02em; }
        h2 { color: #374151 !important; font-weight: 700; }
        h3 { color: #6b7280 !important; font-weight: 600; }

        /* ── Caption ── */
        .stCaption, [data-testid="stCaptionContainer"] p {
            color: #9ca3af !important;
            font-size: 13px !important;
        }

        /* ── Buttons ── */
        .stButton button {
            background: #1e3a5f;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .stButton button:hover {
            background: #243b5e;
            box-shadow: 0 4px 12px rgba(30,58,95,0.25);
        }

        /* ── Spinner ── */
        .stSpinner > div { border-top-color: #3b82f6 !important; }

        /* ── Info boxes ── */
        [data-testid="stInfo"] {
            background-color: #eff6ff !important;
            border: 1px solid #bfdbfe !important;
            border-radius: 10px !important;
            color: #1e40af !important;
        }

        /* ── Warning boxes ── */
        [data-testid="stWarning"] {
            background-color: #fffbeb !important;
            border: 1px solid #fde68a !important;
            border-radius: 10px !important;
        }

        /* ── Expander ── */
        [data-testid="stExpander"] {
            border: 1px solid #e5e7eb !important;
            border-radius: 10px !important;
            background-color: #ffffff !important;
        }

        /* ── Selectbox / Multiselect ── */
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background-color: #ffffff;
            border-color: #d1d5db;
            border-radius: 8px;
        }

        /* ── Multiselect pills ── */
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: #eff6ff !important;
            border: 1px solid #bfdbfe !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #1e40af !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] [role="button"] {
            color: #3b82f6 !important;
        }

        /* ── Slider ── */
        [data-testid="stSlider"] [class*="thumb"] { background-color: #3b82f6 !important; }
        [data-testid="stSlider"] [class*="track"] { background-color: #3b82f6 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def navbar(current: str = "") -> None:
    """Full-width dark navy navigation bar. Pass current= the label of the active page."""
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
                f'<a href="{path}" style="'
                f'background:rgba(255,255,255,0.15);color:#ffffff;'
                f'padding:6px 14px;border-radius:6px;'
                f'font-size:13px;font-weight:600;'
                f'text-decoration:none;white-space:nowrap;'
                f'border:1px solid rgba(255,255,255,0.2);">'
                f'{label}</a>'
            )
        else:
            links += (
                f'<a href="{path}" class="cp-nav-link" style="'
                f'color:rgba(255,255,255,0.72);padding:6px 10px;border-radius:6px;'
                f'font-size:13px;font-weight:400;'
                f'text-decoration:none;white-space:nowrap;">'
                f'{label}</a>'
            )

    st.markdown(
        f"""
        <div style="
            width:100vw;position:relative;left:50%;transform:translateX(-50%);
            background:#1e3a5f;border-bottom:1px solid rgba(255,255,255,0.08);
            padding:0 2rem;height:54px;
            display:flex;align-items:center;justify-content:space-between;
            box-sizing:border-box;margin-bottom:1.5rem;
        ">
            <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
                <span style="font-size:20px">⚓</span>
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
            <h1 style="margin:0;padding:0;color:#111827;font-size:2rem;font-weight:800;">{title}</h1>
            <p style="margin:4px 0 0 0;color:#6b7280;font-size:14px;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
