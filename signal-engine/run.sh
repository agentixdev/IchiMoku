#!/usr/bin/env bash
# Cron wrapper for the Ichimoku signal engine.
# Secrets live in secrets.env (gitignored) — NOT in this tracked file.
set -euo pipefail
cd "$(dirname "$0")"

# Load secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) from an untracked file.
if [ -f ./secrets.env ]; then
  set -a; . ./secrets.env; set +a
fi

# ── Destination ──────────────────────────────────────────────────
export PROVIDER="telegram"

# ── What to watch ────────────────────────────────────────────────
# EASY: to add a symbol, just append it to SYMBOLS (comma-separated).
# With EXCHANGE=yahoo you can mix crypto + forex + stocks in one list:
#   crypto  -> BTC-USD, ETH-USD, SOL-USD
#   forex   -> EURUSD=X, GBPUSD=X, USDJPY=X
#   stocks  -> AAPL, TSLA, SPY
export EXCHANGE="yahoo"               # yahoo | binance | binancefutures | bybit
export SYMBOLS="BTC-USD,ETH-USD,EURUSD=X"
export TIMEFRAME="1d"                 # Daily  (yahoo supports 1m/5m/15m/30m/1h/1d)
export POS_SIZE="1"

# Alternatives if you prefer a specific exchange instead of Yahoo:
#   export EXCHANGE="binancefutures"; export SYMBOLS="BTCUSD_PERP,ETHUSD_PERP"   # Binance COIN-M (USD)
#   export EXCHANGE="binance";        export SYMBOLS="BTCUSDT,ETHUSDT"           # Binance spot (USDT)

# export DRY_RUN="1"                  # uncomment to test without sending

python3 ichimoku_engine.py >> engine.log 2>&1
