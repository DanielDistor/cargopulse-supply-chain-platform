import pytest
from services.aisstream import parse_position_report, make_port_bounding_box


def test_parse_valid_position_report():
    message = {
        "MessageType": "PositionReport",
        "MetaData": {
            "MMSI": 123456789,
            "ShipName": "EVER GIVEN  ",
            "time_utc": "2024-01-01T12:00:00Z",
        },
        "Message": {
            "PositionReport": {
                "Latitude": 31.20,
                "Longitude": 121.50,
                "Sog": 12.5,
                "TrueHeading": 270,
                "NavigationalStatus": 0,
            }
        },
    }
    result = parse_position_report(message)
    assert result is not None
    assert result["mmsi"] == "123456789"
    assert result["name"] == "EVER GIVEN"
    assert result["lat"] == 31.20
    assert result["lon"] == 121.50
    assert result["speed"] == 12.5
    assert result["heading"] == 270


def test_parse_wrong_message_type_returns_none():
    message = {"MessageType": "StaticData", "MetaData": {}, "Message": {}}
    assert parse_position_report(message) is None


def test_parse_malformed_message_returns_none():
    assert parse_position_report({}) is None
    assert parse_position_report({"MessageType": "PositionReport"}) is None


def test_make_port_bounding_box_structure():
    bbox = make_port_bounding_box(lat=31.2, lon=121.5, radius_deg=0.5)
    assert len(bbox) == 2
    assert bbox[0] == [30.7, 121.0]
    assert bbox[1] == [31.7, 122.0]


def test_make_port_bounding_box_default_radius():
    bbox = make_port_bounding_box(lat=0.0, lon=0.0)
    assert bbox[0] == [-0.5, -0.5]
    assert bbox[1] == [0.5, 0.5]
