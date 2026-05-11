import pytest
from unittest.mock import patch, MagicMock
import config


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    import db
    db.init_db()


def _make_snap(last=105.0, prev_close=100.0, premarket_vol=200_000):
    return {"last": last, "prev_close": prev_close, "premarket_volume": premarket_vol}


def _make_daily_bars(avg_vol=1_000_000):
    import pandas as pd
    return pd.DataFrame({"volume": [avg_vol] * 30})


def test_gap_pct_calculation():
    import scanner
    assert abs(scanner._gap_pct(105.0, 100.0) - 0.05) < 0.0001


def test_scanner_gap_filter(monkeypatch):
    import scanner
    # Stock with only 1% gap — below MIN_GAP_PCT=2%
    monkeypatch.setattr(scanner, "_get_snapshot", lambda s: _make_snap(last=101.0))
    monkeypatch.setattr(scanner, "_get_avg_daily_volume", lambda s: 1_000_000)
    result = scanner._evaluate_candidate("TSLA", 100.0)
    assert result is None  # excluded


def test_scanner_volume_filter(monkeypatch):
    import scanner
    # Gap OK but avg daily volume too low
    monkeypatch.setattr(scanner, "_get_snapshot", lambda s: _make_snap())
    monkeypatch.setattr(scanner, "_get_avg_daily_volume", lambda s: 100_000)
    result = scanner._evaluate_candidate("TSLA", 100.0)
    assert result is None


def test_scanner_price_floor(monkeypatch):
    import scanner
    monkeypatch.setattr(scanner, "_get_snapshot", lambda s: _make_snap(last=5.0, prev_close=4.0))
    monkeypatch.setattr(scanner, "_get_avg_daily_volume", lambda s: 1_000_000)
    result = scanner._evaluate_candidate("TSLA", 4.0)
    assert result is None  # price below MIN_PRICE


def test_scanner_includes_valid_candidate(monkeypatch):
    import scanner
    monkeypatch.setattr(scanner, "_get_snapshot", lambda s: _make_snap())
    monkeypatch.setattr(scanner, "_get_avg_daily_volume", lambda s: 1_000_000)
    result = scanner._evaluate_candidate("TSLA", 100.0)
    assert result is not None
    assert result["symbol"] == "TSLA"
    assert result["gap_pct"] > 0


def test_news_conviction_boost(monkeypatch):
    import scanner
    monkeypatch.setattr(scanner, "_fetch_headlines", lambda: [
        "AAPL earnings beat expectations by 20%",
        "Market steady",
    ])
    score = scanner._conviction_score("AAPL")
    assert score == 1  # catalyst found


def test_news_conviction_skip(monkeypatch):
    import scanner
    monkeypatch.setattr(scanner, "_fetch_headlines", lambda: [
        "AAPL SEC fraud investigation launched",
    ])
    score = scanner._conviction_score("AAPL")
    assert score == -1  # negative news


def test_news_no_news_zero(monkeypatch):
    import scanner
    monkeypatch.setattr(scanner, "_fetch_headlines", lambda: [
        "Oil prices rise on Middle East tensions",
    ])
    score = scanner._conviction_score("AAPL")
    assert score == 0  # no news about AAPL


def test_run_scan_returns_watchlist(monkeypatch):
    import scanner
    candidates = [
        {"symbol": "TSLA", "gap_pct": 0.03, "premarket_volume": 300_000, "conviction_score": 1},
        {"symbol": "NVDA", "gap_pct": 0.025, "premarket_volume": 200_000, "conviction_score": 0},
    ]
    monkeypatch.setattr(scanner, "_get_candidates", lambda: candidates)
    monkeypatch.setattr(scanner, "_fetch_headlines", lambda: [])
    watchlist = scanner.run_scan()
    # Core always included
    assert "SPY" in watchlist
    assert "QQQ" in watchlist
    # Dynamic candidates included (up to MAX_SCAN_CANDIDATES)
    assert "TSLA" in watchlist or "NVDA" in watchlist


def test_run_scan_limits_candidates(monkeypatch):
    import scanner
    # 5 candidates but max is 3
    candidates = [
        {"symbol": f"SYM{i}", "gap_pct": 0.05, "premarket_volume": 500_000, "conviction_score": 1}
        for i in range(5)
    ]
    monkeypatch.setattr(scanner, "_get_candidates", lambda: candidates)
    monkeypatch.setattr(scanner, "_fetch_headlines", lambda: [])
    watchlist = scanner.run_scan()
    dynamic = [s for s in watchlist if s not in config.CORE_WATCHLIST]
    assert len(dynamic) <= config.MAX_SCAN_CANDIDATES
