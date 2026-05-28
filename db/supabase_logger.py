"""
Supabase logger — persists vessel activity snapshots via the REST API.

Uses httpx (already in requirements) over HTTPS instead of psycopg2/TCP,
which avoids the IPv6 connectivity issue on Streamlit Cloud.

Secrets needed in .env / Streamlit Cloud secrets:
  SUPABASE_URL = "postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres"
  SUPABASE_KEY = "<publishable key>"   # Settings → API Keys → Publishable key
"""
import os
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

try:
    import httpx
    _HTTPX_OK = True
except ImportError:
    _HTTPX_OK = False


# ── Credential helpers ────────────────────────────────────────────────────────

def _get_secret(key: str) -> str:
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, "")
    except Exception:
        return ""


def _api_base() -> str:
    """Derive REST base URL from the postgres connection string."""
    url = _get_secret("SUPABASE_URL")
    m = re.search(r'db\.([a-z0-9]+)\.supabase\.co', url)
    return f"https://{m.group(1)}.supabase.co" if m else ""


def _key() -> str:
    return _get_secret("SUPABASE_KEY")


def _headers() -> dict:
    k = _key()
    return {
        "apikey":        k,
        "Authorization": f"Bearer {k}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def test_connection() -> dict:
    """Return a status dict. Safe to call from the UI."""
    base = _api_base()
    key  = _key()
    if not _HTTPX_OK:
        return {"ok": False, "error": "httpx not installed"}
    if not base:
        return {"ok": False, "error": "SUPABASE_URL not set or can't parse project ref"}
    if not key:
        return {"ok": False, "error": "SUPABASE_KEY not set"}
    try:
        r = httpx.get(
            f"{base}/rest/v1/vessel_activity",
            headers=_headers(),
            params={"select": "id", "limit": "1"},
            timeout=5,
        )
        if r.status_code == 200:
            return {"ok": True, "error": ""}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def log_snapshot(total: int) -> None:
    """
    Insert one row per page load, but skip if a row was already written
    in the last 60 seconds (guards against rapid refresh spam).
    """
    if not _HTTPX_OK:
        return
    base = _api_base()
    key  = _key()
    if not base or not key:
        return
    try:
        since = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = httpx.get(
            f"{base}/rest/v1/vessel_activity",
            headers=_headers(),
            params={"select": "id", "logged_at": f"gte.{since}", "limit": "1"},
            timeout=5,
        )
        if r.status_code == 200 and r.json():
            return  # already logged in the last minute — skip
        httpx.post(
            f"{base}/rest/v1/vessel_activity",
            headers=_headers(),
            json={"total": int(total)},
            timeout=5,
        )
    except Exception:
        pass


def get_last_24h_activity() -> list:
    """
    Returns raw snapshot rows from the last 24 hours, oldest first.
    Each row dict: {"logged_at": str, "total": int}
    """
    if not _HTTPX_OK:
        return []
    base = _api_base()
    if not base or not _key():
        return []
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = httpx.get(
            f"{base}/rest/v1/vessel_activity",
            headers=_headers(),
            params={"select": "logged_at,total",
                    "logged_at": f"gte.{since}",
                    "order": "logged_at.asc"},
            timeout=10,
        )
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def get_daily_activity(days: int = 7) -> list:
    """
    Returns one row per calendar day for the last `days` days.
    Each row dict: {"day": "2024-05-28", "avg_total": float, "samples": int}
    """
    if not _HTTPX_OK:
        return []
    base = _api_base()
    if not base or not _key():
        return []
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = httpx.get(
            f"{base}/rest/v1/vessel_activity",
            headers=_headers(),
            params={"select": "logged_at,total",
                    "logged_at": f"gte.{since}",
                    "order": "logged_at.asc",
                    "limit": "10000"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        buckets: dict = defaultdict(list)
        for row in r.json():
            buckets[row["logged_at"][:10]].append(row["total"])
        return [
            {"day": day, "avg_total": round(sum(v) / len(v), 1), "samples": len(v)}
            for day, v in sorted(buckets.items())
        ]
    except Exception:
        return []


def get_hourly_activity() -> list:
    """
    Returns up to 24 rows, one per UTC hour, with average vessel count.
    Each row dict: {"hour": int, "avg_total": float, "samples": int}
    """
    if not _HTTPX_OK:
        return []
    base = _api_base()
    if not base or not _key():
        return []
    try:
        r = httpx.get(
            f"{base}/rest/v1/vessel_activity",
            headers=_headers(),
            params={"select": "logged_at,total",
                    "order": "logged_at.asc",
                    "limit": "10000"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        buckets: dict = defaultdict(list)
        for row in r.json():
            buckets[int(row["logged_at"][11:13])].append(row["total"])
        return [
            {"hour": h, "avg_total": round(sum(v) / len(v), 1), "samples": len(v)}
            for h, v in sorted(buckets.items())
        ]
    except Exception:
        return []
