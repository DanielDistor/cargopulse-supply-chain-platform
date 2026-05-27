import pytest
from services.congestion import (
    haversine_km,
    count_vessels_near_port,
    compute_congestion_score,
    congestion_label,
    congestion_color,
)


def test_haversine_same_point_is_zero():
    assert haversine_km(31.2, 121.5, 31.2, 121.5) == 0.0


def test_haversine_known_distance():
    # Shanghai (31.2, 121.5) to Ningbo (29.87, 121.55) great-circle is ~148 km
    dist = haversine_km(31.2, 121.5, 29.87, 121.55)
    assert 130 < dist < 170


def test_count_vessels_near_port_includes_close():
    vessels = [{"lat": 31.2, "lon": 121.5}]
    count = count_vessels_near_port(vessels, port_lat=31.2, port_lon=121.5, radius_km=50)
    assert count == 1


def test_count_vessels_near_port_excludes_far():
    vessels = [{"lat": 0.0, "lon": 0.0}]
    count = count_vessels_near_port(vessels, port_lat=31.2, port_lon=121.5, radius_km=50)
    assert count == 0


def test_count_vessels_skips_missing_coords():
    vessels = [{"lat": None, "lon": None}, {"lat": 31.2, "lon": 121.5}]
    count = count_vessels_near_port(vessels, port_lat=31.2, port_lon=121.5, radius_km=50)
    assert count == 1


def test_congestion_score_zero_vessels_is_zero():
    score = compute_congestion_score(waiting_vessels=0, capacity_baseline=50, wave_height_m=None)
    assert score == 0


def test_congestion_score_at_capacity_is_100():
    score = compute_congestion_score(waiting_vessels=50, capacity_baseline=50, wave_height_m=None)
    assert score == 100


def test_congestion_score_caps_at_100():
    score = compute_congestion_score(waiting_vessels=200, capacity_baseline=50, wave_height_m=None)
    assert score == 100


def test_congestion_score_weather_penalty_increases_score():
    base = compute_congestion_score(40, 50, wave_height_m=None)
    penalized = compute_congestion_score(40, 50, wave_height_m=3.5)
    assert penalized > base


def test_congestion_label_boundaries():
    assert congestion_label(0) == "Clear"
    assert congestion_label(30) == "Clear"
    assert congestion_label(31) == "Moderate"
    assert congestion_label(60) == "Moderate"
    assert congestion_label(61) == "High"
    assert congestion_label(85) == "High"
    assert congestion_label(86) == "Critical"
    assert congestion_label(100) == "Critical"


def test_congestion_color_returns_string():
    for score in [0, 30, 60, 85, 100]:
        assert congestion_color(score).startswith("#")
