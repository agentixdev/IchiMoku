#!/usr/bin/env bash
# Wrapper for cron. Edit the values below, make executable (chmod +x run.sh),
# then schedule it (see crontab examples in README).
set -euo pipefail
cd "$(dirname "$0")"

# ── WhatsApp gateway ─────────────────────────────────────────────
export WA_PROVIDER="whapi"            # or "wassenger"
export WA_TOKEN="your-gateway-api-token"
export WA_GROUP_ID="120363xxxxxxxxxxxx@g.us"

# ── What to watch ────────────────────────────────────────────────
export SYMBOLS="BTCUSDT,ETHUSDT"      # edit to your pairs
export TIMEFRAME="1h"                 # 1m,5m,15m,30m,1h,4h,1d ...
export EXCHANGE="bybit"               # "bybit" (broad access) or "binance"
export POS_SIZE="1"

# export DRY_RUN="1"                  # uncomment to test without sending

python3 ichimoku_engine.py >> engine.log 2>&1
