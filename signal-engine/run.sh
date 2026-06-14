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
# Each symbol can carry its own timeframe + exchange:  symbol:timeframe:exchange
# (omit parts to use the global TIMEFRAME / EXCHANGE defaults below).
#
# BTC = TradingView "BTCUSD.P" = Binance COIN-M perpetual BTCUSD_PERP, on 4h:
export SYMBOLS="BTCUSD_PERP:4h:binancefutures"
#
# To add more later, comma-separate. Examples (note Yahoo has no 4h — use 1h/1d there):
#   export SYMBOLS="BTCUSD_PERP:4h:binancefutures,ETHUSD_PERP:4h:binancefutures"
#   export SYMBOLS="BTCUSD_PERP:4h:binancefutures,EURUSD=X:1d:yahoo,ETH-USD:1d:yahoo"

# Global defaults (used when a symbol omits its :timeframe:exchange)
export TIMEFRAME="4h"
export EXCHANGE="binancefutures"      # yahoo | binance | binancefutures | bybit
export POS_SIZE="1"

# export DRY_RUN="1"                  # uncomment to test without sending

python3 ichimoku_engine.py >> engine.log 2>&1
