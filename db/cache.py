import sqlite3
import json
import time
import os

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "cache.db")


def _db_path() -> str:
    path = os.environ.get("CACHE_DB_PATH", "").strip()
    return path if path else _DEFAULT_DB


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=10)  # wait up to 10s for write lock
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            key        TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            fetched_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get(key: str, ttl_seconds: int) -> dict | None:
    """Return cached data if it exists and is within TTL, else None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT data, fetched_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    data, fetched_at = row
    if time.time() - fetched_at > ttl_seconds:
        return None
    return json.loads(data)


def set(key: str, data: dict) -> None:
    """Write data to cache with current timestamp."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), int(time.time())),
        )


def get_stale(key: str) -> dict | None:
    """Return cached data regardless of age (fallback when API is down)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT data FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def get_age_seconds(key: str) -> int | None:
    """Return how many seconds ago this key was last written."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT fetched_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    return int(time.time() - row[0])
