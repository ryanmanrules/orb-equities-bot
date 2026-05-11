import config
import db


def test_init_creates_tables():
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "trades" in tables
    assert "bot_state" in tables
    assert "events" in tables
    assert "opening_ranges" in tables
    assert "watchlist_log" in tables


def test_insert_and_close_trade():
    tid = db.insert_trade("AAPL", 150.0, 10, 1500.0, 148.0, 154.0, 1, "paper")
    assert tid > 0
    db.close_trade(tid, 154.0, "take_profit")
    trades = db.get_closed_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"
    assert trades[0]["exit_reason"] == "take_profit"


def test_set_and_get_state():
    db.set_state("regime", "cautious")
    state = db.get_state()
    assert state["regime"]["value"] == "cautious"


def test_log_and_get_event():
    db.log_event("circuit_breaker", -0.04, "daily_loss")
    events = db.get_events(limit=5)
    assert len(events) == 1
    assert events[0]["event_type"] == "circuit_breaker"


def test_upsert_opening_range():
    db.upsert_opening_range("2026-05-11", "SPY", 520.0, 518.0)
    ranges = db.get_opening_ranges("2026-05-11")
    assert ranges["SPY"]["range_high"] == 520.0
    assert ranges["SPY"]["range_low"] == 518.0


def test_log_watchlist():
    db.log_watchlist_entry("2026-05-11", "AAPL", 3.5, 1500000, 1, True)
    rows = db.get_watchlist_log("2026-05-11")
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["conviction_score"] == 1
