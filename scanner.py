import logging
import xml.etree.ElementTree as ET
import urllib.request
from datetime import date

import config
import db

logger = logging.getLogger("scanner")

# Keywords for conviction scoring
_POSITIVE_KEYWORDS = [
    "earnings beat", "revenue beat", "raised guidance", "fda approval",
    "analyst upgrade", "buy rating", "price target raised", "merger", "acquisition",
    "record revenue", "record earnings", "stock split",
]
_NEGATIVE_KEYWORDS = [
    "sec investigation", "fraud", "bankruptcy", "downgrade", "miss",
    "earnings miss", "revenue miss", "recall", "lawsuit", "criminal",
    "lowered guidance", "job cuts",
]


def _gap_pct(current: float, prev_close: float) -> float:
    return (current - prev_close) / prev_close


def _get_snapshot(symbol: str) -> dict:
    """Wrapper — replaced in tests."""
    import data
    return data.get_premarket_snapshot(symbol)


def _get_avg_daily_volume(symbol: str) -> float:
    """Return 30-day avg daily volume."""
    import data
    df = data.fetch_daily_bars(symbol, days=30)
    if df.empty:
        return 0.0
    return float(df["volume"].mean())


def _evaluate_candidate(symbol: str, prev_close: float) -> dict | None:
    """Return candidate dict if stock passes all filters, else None."""
    try:
        snap = _get_snapshot(symbol)
        last = snap["last"]
        if last < config.MIN_PRICE or last > config.MAX_PRICE:
            return None
        gap = _gap_pct(last, prev_close)
        if gap < config.MIN_GAP_PCT:
            return None
        avg_vol = _get_avg_daily_volume(symbol)
        if avg_vol < config.MIN_AVG_DAILY_VOLUME:
            return None
        pm_vol = snap["premarket_volume"]
        return {
            "symbol": symbol,
            "gap_pct": round(gap, 4),
            "premarket_volume": pm_vol,
            "last": last,
        }
    except Exception as e:
        logger.warning(f"scanner: error evaluating {symbol}: {e}")
        return None


def _get_candidates() -> list:
    """Scan liquid stock universe for gap+volume candidates."""
    import data as data_module
    universe = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
        "AMD", "INTC", "NFLX", "PLTR", "SMCI", "ARM", "MSTR",
        "BAC", "JPM", "XOM", "CVX", "DIS", "UBER",
    ]
    candidates = []
    for sym in universe:
        try:
            snap = data_module.get_premarket_snapshot(sym)
            prev = snap["prev_close"]
            result = _evaluate_candidate(sym, prev)
            if result:
                candidates.append(result)
        except Exception:
            pass
    return sorted(candidates, key=lambda x: x["gap_pct"], reverse=True)


def _fetch_rss_titles(url: str) -> list:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            tree = ET.fromstring(resp.read())
        titles = []
        for item in tree.iter("item"):
            title = item.findtext("title")
            if title:
                titles.append(title.strip())
        return titles[:20]
    except Exception as e:
        logger.warning(f"scanner: RSS fetch failed ({url}): {e}")
        return []


def _fetch_headlines() -> list:
    """Fetch headlines from all configured RSS feeds."""
    headlines = []
    for feed in config.NEWS_RSS_FEEDS:
        for title in _fetch_rss_titles(feed):
            if title not in headlines:
                headlines.append(title)
            if len(headlines) >= 30:
                return headlines
    return headlines


def _conviction_score(symbol: str) -> int:
    """
    Return:
      1  — positive catalyst found
      0  — no news
     -1  — negative news (skip stock)
    """
    headlines = _fetch_headlines()
    ticker = symbol.split("/")[0].upper()
    relevant = [h for h in headlines if ticker in h.upper()]
    if not relevant:
        return 0
    text = " ".join(relevant).lower()
    if any(kw in text for kw in _NEGATIVE_KEYWORDS):
        return -1
    if any(kw in text for kw in _POSITIVE_KEYWORDS):
        return 1
    return 0


def run_scan() -> list:
    """
    Run the full premarket scan. Returns watchlist (list of symbol strings).
    SPY/QQQ always included. Up to MAX_SCAN_CANDIDATES dynamic additions.
    Logs results to DB.
    """
    today = str(date.today())
    candidates = _get_candidates()
    watchlist = list(config.CORE_WATCHLIST)
    added = 0

    for c in candidates:
        if added >= config.MAX_SCAN_CANDIDATES:
            break
        symbol = c["symbol"]
        score = _conviction_score(symbol)
        included = score >= 0  # skip -1 (negative news)
        db.log_watchlist_entry(
            today, symbol, c["gap_pct"], c["premarket_volume"], score, included
        )
        if included and symbol not in watchlist:
            c["conviction_score"] = score
            watchlist.append(symbol)
            added += 1
            logger.info(
                f"scanner: added {symbol} gap={c['gap_pct']:.1%} "
                f"conviction={score}"
            )

    logger.info(f"scanner: watchlist={watchlist}")
    return watchlist
