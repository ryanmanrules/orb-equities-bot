# Equities ORB Trading Bot

An automated opening-range-breakout (ORB) trading system for US equities, built on Alpaca's paper trading API. Built to explore what actually breaks when a rules-based strategy runs continuously instead of just in a backtest.

## What it does

- Scans and trades an opening-range-breakout strategy on a configurable watchlist
- Runs unattended on a schedule, with a live web dashboard for monitoring positions, P&L, and bot health
- Uses Claude (Anthropic API) for market regime classification, feeding that signal into trade filtering and periodic strategy tuning
- Emergency-stop mechanism for halting all trading instantly
- Telegram notifications for trade events and health alerts
- Append-only, structured JSON decision logs for every trade decision, independent of the trade outcome
- Replay mode to re-run historical decision logs for debugging and strategy review
- Automated SQLite database backups with retention

## Stack

- Python
- Alpaca (`alpaca-py`) for market data and paper trade execution
- Flask for the monitoring dashboard
- Anthropic API (Claude) for regime detection and tuning assistance
- SQLite for trade/decision storage
- `schedule` for the run loop, `pytest` for tests

## Status

Currently running in paper trading only. No live capital is deployed.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your own Alpaca paper API keys, Anthropic API key, and (optional) Telegram credentials
3. `python bot.py` to run the bot, `python dashboard.py` to run the monitoring dashboard
