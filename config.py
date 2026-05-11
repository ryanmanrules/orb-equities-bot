import os

# Alpaca
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = True

# Strategy
ORB_MINUTES = 15
MAX_OPEN_POSITIONS = 3
RISK_PER_TRADE_PCT = 0.01        # 1% of equity
TAKE_PROFIT_MULTIPLIER = 2.0     # 2× range width
STOP_BUFFER_CENTS = 0.05         # 5 cents below range low
MAX_HOLD_MINUTES = 120
EOD_CLOSE_TIME = "15:45"         # ET — "HH:MM"
CHASE_LIMIT_PCT = 0.005          # 0.5% — max entry distance from range high

# Scanner
MIN_GAP_PCT = 0.02
MIN_PREMARKET_VOLUME_MULTIPLIER = 2.0
MIN_AVG_DAILY_VOLUME = 500_000
MIN_PRICE = 10.0
MAX_PRICE = 500.0
MAX_SCAN_CANDIDATES = 3
CORE_WATCHLIST = ["SPY", "QQQ"]

# Safety
DAILY_LOSS_CIRCUIT_BREAKER_PCT = 0.03   # 3% daily loss limit

# Regime
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REGIME_MODEL = "claude-haiku-4-5"
REGIME_CHECK_HOUR = 7            # 7:00am ET

# Dashboard
PAPER_STARTING_BALANCE = 2000.0
DASHBOARD_PORT = 5001
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")

# Paths
DB_PATH = os.path.join(os.path.dirname(__file__), "trades.db")
LOG_PATH = os.path.join(os.path.dirname(__file__), "bot.log")

# News RSS feeds for conviction scoring
NEWS_RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
]

def validate_config():
    if not ALPACA_API_KEY:
        raise ValueError("ALPACA_API_KEY not set")
    if not ALPACA_SECRET_KEY:
        raise ValueError("ALPACA_SECRET_KEY not set")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
