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
export SYMBOLS="BTCUSDT,ETHUSDT"
export TIMEFRAME="1d"                 # Daily
export EXCHANGE="binance"             # or "bybit" (use bybit if VPS is US-based)
export POS_SIZE="1"

# export DRY_RUN="1"                  # uncomment to test without sending

python3 ichimoku_engine.py >> engine.log 2>&1
