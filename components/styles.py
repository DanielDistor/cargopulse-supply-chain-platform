import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Page chrome ── */
        .stApp { background-color: #0f1117; }
        header[data-testid="stHeader"] { background-color: #0f1117; border-bottom: 1px solid #1e2736; }

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

        /* ── Slider ── */
        [data-testid="stSlider"] [class*="thumb"] { background-color: #00d4ff !important; }
        [data-testid="stSlider"] [class*="track"] { background-color: #00d4ff !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    """Render a styled page header with accent line."""
    st.markdown(
        f"""
        <div style="
            border-left: 4px solid #00d4ff;
            padding-left: 16px;
            margin-bottom: 8px;
        ">
            <h1 style="margin:0; padding:0; color:#e8eaed; font-size:2rem; font-weight:800;">{title}</h1>
            <p style="margin:4px 0 0 0; color:#5a6a7e; font-size:14px;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
