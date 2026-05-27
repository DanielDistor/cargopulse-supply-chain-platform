import streamlit as st


def kpi_card(label: str, value: str, delta: str | None = None, color: str = "#2196f3") -> None:
    """Render a styled KPI card using st.metric (wrapper for consistency)."""
    st.metric(label=label, value=value, delta=delta)
