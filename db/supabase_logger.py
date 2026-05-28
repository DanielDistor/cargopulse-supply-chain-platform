"""
Supabase logger — persists vessel activity snapshots to PostgreSQL.

Each fresh AIS fetch writes one row (total vessel count + timestamp).
The dashboard reads these rows to power two charts:
  - Fleet Activity Last 7 Days  (daily average)
  - Fleet Activity by Hour       (hourly average across all data)

Connection URL is read from:
  1. SUPABASE_URL env var  (local .env)
  2. st.secrets["SUPABASE_URL"]  (Streamlit Cloud)

All functions are best-effort — any failure is silently swallowed so a
DB outage never breaks the live vessel feed.
"""
import os

_PSYCOPG2_OK = False
try:
    import psycopg2
    _PSYCOPG2_OK = True
except ImportError:
    pass


def _url() -> str:
    url = os.getenv("SUPABASE_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get("SUPABASE_URL", "")
    except Exception:
        return ""


def _connect():
    """Return a fresh psycopg2 connection, or None if unavailable."""
    if not _PSYCOPG2_OK:
        return None
    u = _url()
    if not u:
        return None
    try:
        return psycopg2.connect(u, connect_timeout=5, sslmode="require")
    except Exception:
        try:
            # Fallback without explicit sslmode (some connection strings include it already)
            return psycopg2.connect(u, connect_timeout=5)
        except Exception:
            return None


def _ensure_table(conn) -> None:
    """Create vessel_activity table + index if they don't exist yet."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vessel_activity (
                id        SERIAL PRIMARY KEY,
                logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                total     INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_vessel_activity_ts
                ON vessel_activity (logged_at);
        """)
    conn.commit()


def log_snapshot(total: int) -> None:
    """
    Insert one snapshot row with the current vessel count.
    Called after every fresh AIS fetch (~every 15 minutes).
    """
    conn = _connect()
    if conn is None:
        return
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("INSERT INTO vessel_activity (total) VALUES (%s)", (int(total),))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_daily_activity(days: int = 7) -> list:
    """
    Returns up to `days` rows — one per calendar day — with the
    average vessel count for that day.

    Each row dict: {"day": datetime.date, "avg_total": float, "samples": int}
    Returns [] if DB is unreachable or no data exists yet.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    DATE(logged_at AT TIME ZONE 'UTC')  AS day,
                    ROUND(AVG(total)::numeric, 1)       AS avg_total,
                    COUNT(*)                            AS samples
                FROM vessel_activity
                WHERE logged_at > NOW() - INTERVAL %s
                GROUP BY day
                ORDER BY day
            """, (f"{days} days",))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_last_24h_activity() -> list:
    """
    Returns individual snapshot rows from the last 24 hours, oldest first.
    Each row dict: {"logged_at": datetime, "total": int}
    Returns [] if DB is unreachable or no data exists yet.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT logged_at AT TIME ZONE 'UTC' AS logged_at, total
                FROM vessel_activity
                WHERE logged_at > NOW() - INTERVAL '24 hours'
                ORDER BY logged_at
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_hourly_activity() -> list:
    """
    Returns up to 24 rows — one per UTC hour — with the average
    vessel count for that hour across all logged data.

    Each row dict: {"hour": int, "avg_total": float, "samples": int}
    Returns [] if DB is unreachable or no data exists yet.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    EXTRACT(HOUR FROM logged_at AT TIME ZONE 'UTC')::int AS hour,
                    ROUND(AVG(total)::numeric, 1)                        AS avg_total,
                    COUNT(*)                                             AS samples
                FROM vessel_activity
                GROUP BY hour
                ORDER BY hour
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()
