import yfinance as yf
from db import cache

TTL = 24 * 3600  # 24 hours — BDI is published once per day


def get_bdi() -> dict:
    """
    Fetch the Baltic Dry Index via yfinance.
    Returns value, 1-day change, 7-day trend, and 30-day history.
    Falls back to stale cache or null dict on failure.
    """
    cache_key = "bdi_current"
    cached = cache.get(cache_key, TTL)
    if cached:
        return cached

    _null = {
        "value": None,
        "change_1d": None,
        "change_pct_1d": None,
        "trend": "unknown",
        "history": [],
        "dates": [],
    }

    try:
        ticker = yf.Ticker("^BDIY")
        hist = ticker.history(period="30d")
        if hist.empty:
            raise ValueError("Empty BDI response from yfinance")

        closes = hist["Close"]
        latest = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else latest
        week_ago = float(closes.iloc[-5]) if len(closes) >= 5 else float(closes.iloc[0])

        result = {
            "value": latest,
            "change_1d": round(latest - prev, 2),
            "change_pct_1d": round((latest - prev) / prev * 100, 2),
            "trend": "rising" if latest > week_ago else "falling",
            "history": [round(v, 2) for v in closes.tail(30).tolist()],
            "dates": [d.strftime("%Y-%m-%d") for d in closes.index[-30:]],
        }
        cache.set(cache_key, result)
        return result
    except Exception:
        return cache.get_stale(cache_key) or _null
