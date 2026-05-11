import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime, timezone


@pytest.fixture
def mock_trading_client():
    with patch("data._get_trading_client") as m:
        client = MagicMock()
        m.return_value = client
        yield client


@pytest.fixture
def mock_data_client():
    with patch("data._get_data_client") as m:
        client = MagicMock()
        m.return_value = client
        yield client


def test_get_account_returns_equity(mock_trading_client):
    import data
    mock_trading_client.get_account.return_value = MagicMock(equity="2050.00", cash="1000.00")
    account = data.get_account()
    assert account["equity"] == 2050.0
    assert account["cash"] == 1000.0


def test_is_market_open_true(mock_trading_client):
    import data
    mock_trading_client.get_clock.return_value = MagicMock(is_open=True)
    assert data.is_market_open() is True


def test_is_market_open_false(mock_trading_client):
    import data
    mock_trading_client.get_clock.return_value = MagicMock(is_open=False)
    assert data.is_market_open() is False


def test_is_trading_day_true(mock_trading_client):
    import data
    from datetime import date
    mock_trading_client.get_calendar.return_value = [MagicMock()]
    assert data.is_trading_day(date(2026, 5, 11)) is True


def test_is_trading_day_false(mock_trading_client):
    import data
    from datetime import date
    mock_trading_client.get_calendar.return_value = []
    assert data.is_trading_day(date(2026, 5, 9)) is False  # Saturday


def test_fetch_bars_returns_dataframe(mock_data_client):
    import data
    mock_bars = MagicMock()
    mock_df = pd.DataFrame({
        "open": [150.0, 151.0],
        "high": [152.0, 153.0],
        "low": [149.0, 150.5],
        "close": [151.5, 152.5],
        "volume": [100000, 120000],
    }, index=pd.to_datetime(["2026-05-11 09:30:00", "2026-05-11 09:31:00"], utc=True))
    mock_bars.df = mock_df
    mock_data_client.get_stock_bars.return_value = mock_bars
    df = data.fetch_bars("AAPL", limit=2)
    assert isinstance(df, pd.DataFrame)
    assert "close" in df.columns
    assert len(df) == 2


def test_get_premarket_snapshot_returns_dict(mock_data_client):
    import data
    snap = MagicMock()
    snap.latest_trade.price = 150.5
    snap.minute_bar.volume = 50000
    snap.prev_daily_bar.close = 148.0
    mock_data_client.get_stock_snapshot.return_value = {"AAPL": snap}
    result = data.get_premarket_snapshot("AAPL")
    assert result["last"] == 150.5
    assert result["prev_close"] == 148.0
    assert result["premarket_volume"] == 50000


def test_place_market_order_returns_order_id(mock_trading_client):
    import data
    mock_trading_client.submit_order.return_value = MagicMock(id="order-123")
    order_id = data.place_market_order("AAPL", 10, "buy")
    assert order_id == "order-123"


def test_close_symbol_position(mock_trading_client):
    import data
    data.close_symbol_position("AAPL")
    mock_trading_client.close_position.assert_called_once_with("AAPL")
