"""
Maritime & supply chain news feed.

Primary:  NewsAPI.org  (set NEWS_API_KEY in .env — free dev tier, 100 req/day)
Fallback: RSS feeds from Hellenic Shipping News + Splash247  (no key required)

Results are cached for 30 min in SQLite so they survive hot-reloads.
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import TypedDict

import httpx
from db import cache as db_cache


class NewsItem(TypedDict):
    title: str
    source: str
    url: str
    description: str


_QUERY = (
    "port congestion OR shipping delay OR maritime disruption "
    "OR supply chain risk OR Red Sea shipping OR Suez Canal "
    "OR Panama Canal OR freight rates OR vessel"
)

_RSS_FEEDS = [
    ("https://www.hellenicshippingnews.com/feed/",    "Hellenic Shipping News"),
    ("https://splash247.com/feed/",                   "Splash247"),
    ("https://www.seatrade-maritime.com/rss.xml",     "Seatrade Maritime"),
]

_HEADERS = {"User-Agent": "CargoPulse/1.0 (supply chain intelligence platform)"}

_CACHE_KEY = "maritime_news"
_TTL = 30 * 60  # 30 minutes — survives hot-reloads unlike @st.cache_data


# ── Public API ─────────────────────────────────────────────────────────

def get_maritime_news(n: int = 4) -> list[NewsItem]:
    """Return up to *n* recent maritime news items."""
    cached = db_cache.get(_CACHE_KEY, _TTL)
    if cached:
        return cached.get("items", [])[:n]

    api_key = os.getenv("NEWS_API_KEY", "").strip()
    items = _newsapi(api_key, n) if api_key else []
    if not items:
        items = _rss_fallback(n)

    if items:
        # Cache up to 8 so callers can slice without re-fetching
        db_cache.set(_CACHE_KEY, {"items": items[:8]})
        return items[:n]

    # Network failed — serve stale rather than blank
    stale = db_cache.get_stale(_CACHE_KEY)
    return stale.get("items", [])[:n] if stale else []


# ── Providers ──────────────────────────────────────────────────────────

def _newsapi(api_key: str, n: int) -> list[NewsItem]:
    try:
        r = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        _QUERY,
                "sortBy":   "publishedAt",
                "pageSize": n + 4,
                "language": "en",
                "apiKey":   api_key,
            },
            timeout=5,
            headers=_HEADERS,
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])
        return [
            NewsItem(
                title=a["title"],
                source=a["source"]["name"],
                url=a.get("url", ""),
                description=_clean(a.get("description") or "", 120),
            )
            for a in articles
            if a.get("title") and "[Removed]" not in (a.get("title") or "")
        ]
    except Exception:
        return []


def _rss_fallback(n: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    for url, source in _RSS_FEEDS:
        if len(items) >= n:
            break
        try:
            r = httpx.get(url, timeout=4, headers=_HEADERS, follow_redirects=True)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:4]:
                title = _clean(item.findtext("title") or "", 100)
                link  = (item.findtext("link") or "").strip()
                desc  = _clean(item.findtext("description") or "", 120)
                if title:
                    items.append(NewsItem(title=title, source=source, url=link, description=desc))
        except Exception:
            continue
    return items


def _clean(text: str, max_len: int) -> str:
    text = re.sub(r"<[^>]+>", "", text)   # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] + ("…" if len(text) > max_len else "")
