#!/usr/bin/env bash
# Cron wrapper for the screener digest. Reuses the same gateway config.
set -euo pipefail
cd "$(dirname "$0")"

export WA_PROVIDER="whapi"            # or "wassenger"
export WA_TOKEN="your-gateway-api-token"
export WA_GROUP_ID="120363xxxxxxxxxxxx@g.us"

export WATCHLIST="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"
export TIMEFRAME="4h"
export EXCHANGE="bybit"

# export DRY_RUN="1"

python3 digest.py >> digest.log 2>&1
