import time
import pytest
from db import cache


def test_set_and_get_returns_stored_data():
    cache.set("key1", {"value": 42})
    result = cache.get("key1", ttl_seconds=3600)
    assert result == {"value": 42}


def test_get_returns_none_when_expired():
    cache.set("key2", {"value": 99})
    result = cache.get("key2", ttl_seconds=0)
    assert result is None


def test_get_returns_none_when_missing():
    result = cache.get("nonexistent_xyz", ttl_seconds=3600)
    assert result is None


def test_get_stale_returns_data_regardless_of_ttl():
    cache.set("key3", {"value": "old"})
    result = cache.get_stale("key3")
    assert result == {"value": "old"}


def test_get_stale_returns_none_when_never_set():
    result = cache.get_stale("never_set_key_xyz")
    assert result is None


def test_get_age_seconds_returns_elapsed():
    cache.set("key4", {"v": 1})
    age = cache.get_age_seconds("key4")
    assert 0 <= age <= 2


def test_get_age_seconds_returns_none_when_missing():
    result = cache.get_age_seconds("missing_key_xyz")
    assert result is None


def test_set_overwrites_existing():
    cache.set("key5", {"v": 1})
    cache.set("key5", {"v": 2})
    result = cache.get("key5", ttl_seconds=3600)
    assert result == {"v": 2}
