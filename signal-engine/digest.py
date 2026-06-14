#!/usr/bin/env python3
"""
Complementary scheduled SCREENER digest -> WhatsApp.

Unlike ichimoku_engine.py (which fires precise trade signals), this scans a
watchlist and reports each symbol's current Ichimoku bias and whether a fresh
LONG/SHORT setup is active right now. Good for a once-or-twice-daily overview.

Reuses ichimoku_engine for fetching + the same parameters. Pure stdlib.

Extra env vars (plus the WA_* ones from run.sh):
  WATCHLIST   comma list (default = SYMBOLS, else a crypto majors basket)
  TIMEFRAME   default 1h
"""

import os
import sys

import ichimoku_engine as e


def snapshot(candles):
    """Compute the latest-bar Ichimoku screener view."""
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]
    i = len(candles) - 1

    conv = e.donchian(highs, lows, i, e.CONV_PERIODS)
    base = e.donchian(highs, lows, i, e.BASE_PERIODS)
    lead1 = (conv + base) / 2.0
    lead2 = e.donchian(highs, lows, i, e.LEAD2_PERIODS)
    close = closes[i]

    cloud_top = max(e_lead(highs, lows, i - e.D, "1"), e_lead(highs, lows, i - e.D, "2"))
    cloud_bot = min(e_lead(highs, lows, i - e.D, "1"), e_lead(highs, lows, i - e.D, "2"))

    above_cloud = close > cloud_top
    below_cloud = close < cloud_bot
    tk_bull = conv > base
    cloud_bull = lead1 > lead2

    if above_cloud and tk_bull and cloud_bull:
        bias = "🟢 Bullish (above cloud)"
    elif below_cloud and not tk_bull and not cloud_bull:
        bias = "🔴 Bearish (below cloud)"
    else:
        bias = "⚪ Neutral / in-cloud"
    return bias, close


def e_lead(highs, lows, i, which):
    conv = e.donchian(highs, lows, i, e.CONV_PERIODS)
    base = e.donchian(highs, lows, i, e.BASE_PERIODS)
    if which == "1":
        return (conv + base) / 2.0
    return e.donchian(highs, lows, i, e.LEAD2_PERIODS)


def main():
    watch = e.env("WATCHLIST") or e.env("SYMBOLS") or "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"
    symbols = [s.strip() for s in watch.split(",") if s.strip()]
    tf = e.env("TIMEFRAME", "1h").lower()
    exchange = e.env("EXCHANGE", "bybit").lower()

    lines = [f"📋 *Ichimoku digest*  ·  {tf}"]
    for sym in symbols:
        try:
            candles = e.fetch_candles(sym, tf, exchange)
            bias, price = snapshot(candles)
            lines.append(f"{sym}: {bias}  ({e.fmt_num(price)})")
        except Exception as ex:  # noqa: BLE001 - digest should be resilient
            lines.append(f"{sym}: ⚠️ error")
            print(f"[{sym}] {type(ex).__name__}: {ex}", file=sys.stderr)

    text = "\n".join(lines)
    e.send_whatsapp(text)
    print("digest sent" if e.env("DRY_RUN") != "1" else text)


if __name__ == "__main__":
    main()
