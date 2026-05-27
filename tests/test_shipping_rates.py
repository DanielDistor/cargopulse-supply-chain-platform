import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from services.shipping_rates import get_bdi


def test_get_bdi_returns_required_keys():
    mock_hist = pd.DataFrame(
        {"Close": [1200.0, 1250.0, 1300.0, 1350.0, 1400.0, 1450.0]},
        index=pd.date_range("2024-01-01", periods=6),
    )
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_hist

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = get_bdi()

    assert "value" in result
    assert "trend" in result
    assert "change_pct_1d" in result
    assert result["trend"] == "rising"
    assert result["value"] == 1450.0


def test_get_bdi_detects_falling_trend():
    mock_hist = pd.DataFrame(
        {"Close": [1400.0, 1350.0, 1300.0, 1250.0, 1200.0, 1100.0]},
        index=pd.date_range("2024-01-01", periods=6),
    )
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_hist

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = get_bdi()

    assert result["trend"] == "falling"


def test_get_bdi_fallback_on_error():
    with patch("yfinance.Ticker", side_effect=Exception("network error")):
        result = get_bdi()
    assert result["value"] is None
    assert result["trend"] == "unknown"
