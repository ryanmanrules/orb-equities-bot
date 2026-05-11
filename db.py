import sqlite3
import os
from contextlib import contextmanager
import config

@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            entry_price REAL,
            exit_price REAL,
            shares INTEGER,
            size_usd REAL,
            stop_price REAL,
            target_price REAL,
            pnl_usd REAL,
            pnl_pct REAL,
            exit_reason TEXT,
            opened_at TEXT,
            closed_at TEXT,
            mode TEXT,
            conviction_score INTEGER DEFAULT 0,
            entry_order_id TEXT,
            exit_order_id TEXT
        );
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            value REAL,
            note TEXT,
            occurred_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS opening_ranges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            symbol TEXT,
            range_high REAL,
            range_low REAL,
            range_width REAL,
            triggered INTEGER DEFAULT 0,
            UNIQUE(date, symbol)
        );
        CREATE TABLE IF NOT EXISTS watchlist_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            symbol TEXT,
            gap_pct REAL,
            premarket_volume INTEGER,
            conviction_score INTEGER DEFAULT 0,
            included INTEGER DEFAULT 0
        );
        """)
        conn.commit()


def insert_trade(symbol, entry_price, shares, size_usd, stop_price, target_price,
                 conviction_score, mode):
    from datetime import datetime, timezone
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO trades
               (symbol, entry_price, shares, size_usd, stop_price, target_price,
                conviction_score, mode, opened_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, entry_price, shares, size_usd, stop_price, target_price,
             conviction_score, mode, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        return cur.lastrowid


def close_trade(trade_id, exit_price, pnl_pct, exit_reason, exit_order_id=None):
    from datetime import datetime, timezone
    with get_conn() as conn:
        row = conn.execute("SELECT entry_price, shares FROM trades WHERE id=?",
                           (trade_id,)).fetchone()
        pnl_usd = (exit_price - row["entry_price"]) * row["shares"] if row else None
        conn.execute(
            """UPDATE trades SET exit_price=?, pnl_usd=?, pnl_pct=?,
               exit_reason=?, closed_at=?, exit_order_id=? WHERE id=?""",
            (exit_price, pnl_usd, pnl_pct, exit_reason,
             datetime.now(timezone.utc).isoformat(), exit_order_id, trade_id)
        )
        conn.commit()


def get_closed_trades(days=None):
    with get_conn() as conn:
        if days:
            rows = conn.execute(
                "SELECT * FROM trades WHERE exit_reason IS NOT NULL "
                "AND closed_at >= datetime('now', ? || ' days') ORDER BY closed_at DESC",
                (f"-{days}",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades WHERE exit_reason IS NOT NULL "
                "ORDER BY closed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_open_trades():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE exit_reason IS NULL ORDER BY opened_at"
        ).fetchall()
        return [dict(r) for r in rows]


def set_state(key, value):
    from datetime import datetime, timezone
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, str(value), datetime.now(timezone.utc).isoformat())
        )
        conn.commit()


def get_state():
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value, updated_at FROM bot_state").fetchall()
        return {r["key"]: {"value": r["value"], "updated_at": r["updated_at"]} for r in rows}


def log_event(event_type, value, note=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (event_type, value, note) VALUES (?, ?, ?)",
            (event_type, value, note)
        )
        conn.commit()


def get_events(limit=50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY occurred_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_opening_range(date, symbol, range_high, range_low):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO opening_ranges (date, symbol, range_high, range_low, range_width)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(date, symbol) DO UPDATE SET
               range_high=excluded.range_high,
               range_low=excluded.range_low,
               range_width=excluded.range_width""",
            (date, symbol, range_high, range_low, round(range_high - range_low, 4))
        )
        conn.commit()


def get_opening_ranges(date):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM opening_ranges WHERE date=?", (date,)
        ).fetchall()
        return {r["symbol"]: dict(r) for r in rows}


def mark_range_triggered(date, symbol):
    with get_conn() as conn:
        conn.execute(
            "UPDATE opening_ranges SET triggered=1 WHERE date=? AND symbol=?",
            (date, symbol)
        )
        conn.commit()


def log_watchlist_entry(date, symbol, gap_pct, premarket_volume, conviction_score, included):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO watchlist_log
               (date, symbol, gap_pct, premarket_volume, conviction_score, included)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, symbol, gap_pct, premarket_volume, conviction_score, int(included))
        )
        conn.commit()


def get_watchlist_log(date):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist_log WHERE date=? ORDER BY gap_pct DESC", (date,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_daily_pnl(date):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(pnl_usd), 0) as total FROM trades "
            "WHERE exit_reason IS NOT NULL AND DATE(closed_at)=?", (date,)
        ).fetchone()
        return row["total"] if row else 0.0
