import pytest
from unittest.mock import patch, MagicMock
from services.weather import weather_penalty, get_marine_weather


def test_weather_penalty_calm_sea():
    assert weather_penalty(0.5) == 1.0


def test_weather_penalty_light_chop():
    assert weather_penalty(1.5) == 1.1


def test_weather_penalty_moderate_waves():
    assert weather_penalty(2.5) == 1.25


def test_weather_penalty_rough_sea():
    assert weather_penalty(3.5) == 1.5


def test_weather_penalty_none_returns_one():
    assert weather_penalty(None) == 1.0


def test_get_marine_weather_returns_dict_with_required_keys():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "current": {
            "wave_height": 1.2,
            "wave_direction": 180,
            "wave_period": 8.5,
            "wind_wave_height": 0.8,
            "ocean_current_velocity": 0.5,
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        result = get_marine_weather(31.2, 121.5)

    assert result["wave_height_m"] == 1.2
    assert result["wave_direction_deg"] == 180
    assert result["lat"] == 31.2
    assert result["lon"] == 121.5


def test_get_marine_weather_returns_fallback_on_error():
    with patch("httpx.get", side_effect=Exception("network error")):
        result = get_marine_weather(0.0, 0.0)
    assert result["wave_height_m"] is None
    assert result["lat"] == 0.0
