#!/usr/bin/env bash
# Cron wrapper for the screener digest. Reuses the same gateway config.
set -euo pipefail
cd "$(dirname "$0")"

export PROVIDER="telegram"
export TELEGRAM_BOT_TOKEN="123456:ABC-your-bot-token"
export TELEGRAM_CHAT_ID="-1001234567890"
# --- OR WhatsApp gateway ---
# export PROVIDER="whapi"
# export WA_TOKEN="your-gateway-api-token"
# export WA_GROUP_ID="120363xxxxxxxxxxxx@g.us"

export WATCHLIST="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"
export TIMEFRAME="4h"
export EXCHANGE="bybit"

# export DRY_RUN="1"

python3 digest.py >> digest.log 2>&1
