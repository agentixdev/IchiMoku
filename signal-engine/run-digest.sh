#!/usr/bin/env bash
# Cron wrapper for the screener digest. Secrets come from secrets.env (gitignored).
set -euo pipefail
cd "$(dirname "$0")"

if [ -f ./secrets.env ]; then
  set -a; . ./secrets.env; set +a
fi

export PROVIDER="telegram"
export WATCHLIST="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"
export TIMEFRAME="1d"
export EXCHANGE="binance"

# export DRY_RUN="1"

python3 digest.py >> digest.log 2>&1
