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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vessel_types (
            mmsi       TEXT PRIMARY KEY,
            type_code  INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
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


# ── Persistent vessel-type lookup ─────────────────────────────────────────────

def save_vessel_types(mmsi_to_code: dict) -> None:
    """
    Upsert MMSI → AIS type-code pairs into the persistent lookup table.
    Accumulated across all fetches so vessels seen once are remembered forever.
    """
    if not mmsi_to_code:
        return
    now = int(time.time())
    with _connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO vessel_types (mmsi, type_code, updated_at) VALUES (?, ?, ?)",
            [(mmsi, int(code), now) for mmsi, code in mmsi_to_code.items()],
        )


def load_vessel_types(mmsi_list: list) -> dict:
    """
    Return {mmsi: type_code} for every MMSI in mmsi_list that exists in the
    persistent store.  Unknown MMSIs are simply absent from the result.
    """
    if not mmsi_list:
        return {}
    placeholders = ",".join("?" * len(mmsi_list))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT mmsi, type_code FROM vessel_types WHERE mmsi IN ({placeholders})",
            mmsi_list,
        ).fetchall()
    return {mmsi: code for mmsi, code in rows}
