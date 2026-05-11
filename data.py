import logging
import threading
from datetime import date, datetime, timezone, timedelta
import pandas as pd

import config

logger = logging.getLogger("data")

# ── client singletons ──────────────────────────────────────────────────────────

_trading_client = None
_data_client = None
_client_lock = threading.Lock()


def _get_trading_client():
    global _trading_client
    if _trading_client is None:
        with _client_lock:
            if _trading_client is None:
                from alpaca.trading.client import TradingClient
                _trading_client = TradingClient(
                    api_key=config.ALPACA_API_KEY,
                    secret_key=config.ALPACA_SECRET_KEY,
                    paper=config.ALPACA_PAPER,
                )
    return _trading_client


def _get_data_client():
    global _data_client
    if _data_client is None:
        with _client_lock:
            if _data_client is None:
                from alpaca.data.historical import StockHistoricalDataClient
                _data_client = StockHistoricalDataClient(
                    api_key=config.ALPACA_API_KEY,
                    secret_key=config.ALPACA_SECRET_KEY,
                )
    return _data_client


# ── account / clock ────────────────────────────────────────────────────────────

def get_account() -> dict:
    """Return equity and cash as floats."""
    acct = _get_trading_client().get_account()
    return {"equity": float(acct.equity), "cash": float(acct.cash)}


def is_market_open() -> bool:
    return _get_trading_client().get_clock().is_open


def is_trading_day(d: date) -> bool:
    """Return True if Alpaca considers `d` a trading day."""
    from alpaca.trading.requests import GetCalendarRequest
    cal = _get_trading_client().get_calendar(
        filters=GetCalendarRequest(start=str(d), end=str(d))
    )
    return len(cal) > 0


# ── historical bars ────────────────────────────────────────────────────────────

def fetch_bars(symbol: str, limit: int = 30, timeframe_minutes: int = 1) -> pd.DataFrame:
    """Fetch recent 1-minute bars for `symbol`. Returns DataFrame with OHLCV columns."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    tf = TimeFrame(timeframe_minutes, TimeFrameUnit.Minute)
    start = datetime.now(timezone.utc) - timedelta(minutes=limit * timeframe_minutes + 60)
    req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, start=start, limit=limit)
    bars = _get_data_client().get_stock_bars(req)
    df = bars.df
    if df.empty:
        return df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")
    return df.sort_index()


def fetch_daily_bars(symbol: str, days: int = 35) -> pd.DataFrame:
    """Fetch recent daily bars — used for avg volume calculation."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    start = datetime.now(timezone.utc) - timedelta(days=days + 5)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        limit=days,
    )
    bars = _get_data_client().get_stock_bars(req)
    df = bars.df
    if df.empty:
        return df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")
    return df.sort_index()


# ── snapshot (premarket) ───────────────────────────────────────────────────────

def get_premarket_snapshot(symbol: str) -> dict:
    """Return latest trade price, prev close, and premarket volume."""
    from alpaca.data.requests import StockSnapshotRequest
    req = StockSnapshotRequest(symbol_or_symbols=[symbol])
    snaps = _get_data_client().get_stock_snapshot(req)
    snap = snaps.get(symbol)
    if snap is None:
        raise ValueError(f"No snapshot for {symbol}")
    if snap.latest_trade is None or snap.prev_daily_bar is None:
        raise ValueError(f"Incomplete snapshot for {symbol}: missing trade or prior close data")
    return {
        "last": float(snap.latest_trade.price),
        "prev_close": float(snap.prev_daily_bar.close),
        "premarket_volume": int(snap.minute_bar.volume) if snap.minute_bar else 0,
    }


# ── order execution ────────────────────────────────────────────────────────────

def place_market_order(symbol: str, qty: int, side: str) -> str:
    """Place a market DAY order. `side` = 'buy' or 'sell'. Returns order id."""
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    side_lower = side.lower()
    if side_lower not in ("buy", "sell"):
        raise ValueError(f"Invalid order side: {side!r}. Must be 'buy' or 'sell'.")
    s = OrderSide.BUY if side_lower == "buy" else OrderSide.SELL
    req = MarketOrderRequest(symbol=symbol, qty=qty, side=s, time_in_force=TimeInForce.DAY)
    order = _get_trading_client().submit_order(req)
    order_id = str(order.id)
    logger.info(f"data: ORDER {side.upper()} {qty} {symbol} → order_id={order_id}")
    return order_id


def close_symbol_position(symbol: str):
    """Close entire position for symbol via Alpaca."""
    logger.info(f"data: CLOSE POSITION {symbol}")
    _get_trading_client().close_position(symbol)


def get_alpaca_positions() -> dict:
    """Return {symbol: qty} for all open Alpaca positions."""
    positions = _get_trading_client().get_all_positions()
    return {p.symbol: int(float(p.qty)) for p in positions}
