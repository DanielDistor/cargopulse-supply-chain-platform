import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Page chrome ── */
        .stApp { background-color: #0f1117; }
        header[data-testid="stHeader"] { background-color: #0f1117; border-bottom: 1px solid #1e2736; }

        /* ── Hide sidebar and its toggle button entirely ── */
        [data-testid="stSidebar"]       { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebarContent"] { display: none !important; }

        /* ── Top-nav page links ── */
        [data-testid="stPageLink"] { margin: 0 !important; padding: 0 !important; }
        [data-testid="stPageLink"] a,
        [data-testid="stPageLink"] a:visited {
            color: #6b7fa3 !important;
            text-decoration: none !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            padding: 6px 10px !important;
            border-radius: 6px !important;
            white-space: nowrap !important;
            display: block !important;
        }
        [data-testid="stPageLink"] a:hover {
            color: #e8eaed !important;
            background: #1e2736 !important;
        }
        [data-testid="stPageLink"] a[aria-current="page"] {
            color: #00d4ff !important;
            font-weight: 600 !important;
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

        /* ── Multiselect selected pills — override bright cyan default ── */
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


def navbar() -> None:
    """Top navigation bar — brand on the left, page links on the right."""
    brand_col, n1, n2, n3, n4, n5, n6 = st.columns([2.2, 0.9, 1.5, 1.5, 1.4, 1.4, 1.2])
    with brand_col:
        st.markdown(
            '<div style="display:flex;align-items:center;height:36px;">'
            '<span style="color:#e8eaed;font-size:18px;font-weight:800;'
            'letter-spacing:-0.01em">CargoPulse</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    with n1: st.page_link("Home.py",                    label="Home")
    with n2: st.page_link("pages/1_Vessel_Tracking.py", label="Vessel Tracking")
    with n3: st.page_link("pages/2_Port_Congestion.py", label="Port Congestion")
    with n4: st.page_link("pages/3_Delay_Forecast.py",  label="Delay Forecast")
    with n5: st.page_link("pages/4_Supplier_Risk.py",   label="Supplier Risk")
    with n6: st.page_link("pages/5_Risk_Alerts.py",     label="Risk Alerts")
    st.markdown(
        '<hr style="margin:4px 0 20px 0;border:none;border-top:1px solid #1e2736;">',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    """Render a styled page header."""
    st.markdown(
        f"""
        <div style="margin-bottom: 8px;">
            <h1 style="margin:0; padding:0; color:#e8eaed; font-size:2rem; font-weight:800;">{title}</h1>
            <p style="margin:4px 0 0 0; color:#5a6a7e; font-size:14px;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
