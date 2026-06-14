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
# BTC (BTCUSD.P, COIN-M) + ETH (ETHUSDT.P, USD-M) + EURUSD (forex), all on 4h.
# Yahoo has no native 4h, so EURUSD 4h is auto-aggregated from Yahoo 1h.
export SYMBOLS="BTCUSD_PERP:4h:binancefutures,ETHUSDT:4h:binanceusdm,EURUSD=X:4h:yahoo"
#
# Add/remove any symbol by editing the list. More examples:
#   BTCUSDT:4h:binanceusdm        (BTC USD-M perpetual)
#   GBPUSD=X:4h:yahoo , AAPL:1d:yahoo

# Global defaults (used when a symbol omits its :timeframe:exchange)
export TIMEFRAME="4h"
export EXCHANGE="binancefutures"      # yahoo | binance | binancefutures | bybit
export POS_SIZE="1"

# export DRY_RUN="1"                  # uncomment to test without sending

python3 ichimoku_engine.py >> engine.log 2>&1
