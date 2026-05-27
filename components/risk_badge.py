import streamlit as st

COLORS = {
    "LOW": "#4caf50",
    "MEDIUM": "#ffb74d",
    "HIGH": "#ef5350",
    "CRITICAL": "#b71c1c",
    "Clear": "#4caf50",
    "Moderate": "#ffb74d",
    "High": "#ef5350",
    "Critical": "#b71c1c",
}


def risk_badge(label: str) -> None:
    """Render a colored risk badge using st.markdown."""
    color = COLORS.get(label, "#9e9e9e")
    st.markdown(
        f'<span style="background:{color};color:white;padding:3px 10px;'
        f'border-radius:12px;font-weight:700;font-size:13px">{label}</span>',
        unsafe_allow_html=True,
    )
