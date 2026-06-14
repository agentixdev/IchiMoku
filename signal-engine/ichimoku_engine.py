#!/usr/bin/env python3
"""
Ichimoku Signals Final -> WhatsApp, with NO TradingView subscription.

Re-implements the Pine v6 indicator's signal logic (entries, fixed SL exits,
Chikou x Tenkan exits, chop filters, cooldown) directly from free exchange
candles, tracks position state, and pushes any *new* LONG / SHORT / EXIT to the
"Ichimoku" WhatsApp group via a gateway (Whapi / Wassenger).

Designed to run on a schedule (e.g. a VPS cron). Pure standard library — no pip.

Config via environment variables (see run.sh):
  SYMBOLS        comma list, e.g. "BTCUSDT,ETHUSDT"   (default BTCUSDT,ETHUSDT)
  TIMEFRAME      1m,3m,5m,15m,30m,1h,2h,4h,6h,12h,1d  (default 1h)
  EXCHANGE       "bybit" (default) or "binance"
  WA_PROVIDER    "whapi" (default) or "wassenger"
  WA_TOKEN       gateway API token
  WA_GROUP_ID    WhatsApp group id, e.g. 120363...@g.us
  STATE_FILE     path for dedupe state (default ./state.json)
  POS_SIZE       units for P&L (default 1)
  DRY_RUN        "1" to print instead of sending
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

# ── Indicator parameters (match the Pine defaults) ───────────────────────────
CONV_PERIODS = 9
BASE_PERIODS = 26
LEAD2_PERIODS = 52
DISPLACEMENT = 26

USE_KJ_SLOPE = True
KJ_SLOPE_LEN = 4
USE_KUMO_THK = True
KUMO_MIN_PCT = 0.75
USE_TK_SEP = True
TK_MIN_PCT = 0.15
USE_CHIKOU_OS = True
COOLDOWN = 3

D = DISPLACEMENT - 1  # 25

# ── Timeframe maps ───────────────────────────────────────────────────────────
TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60,
          "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440}


def env(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


# ── Candle fetching ──────────────────────────────────────────────────────────
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": _BROWSER_UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Yahoo interval map (covers crypto, forex, stocks, indices in ONE feed)
YAHOO_INT = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "1d": "1d"}


def fetch_candles(symbol, timeframe, exchange, limit=1000):
    """Return oldest-first list of dicts {t,o,h,l,c}, with the in-progress
    (last, still-forming) candle dropped so we only evaluate closed bars.

    exchange:
      yahoo          universal — BTC-USD, ETH-USD, EURUSD=X, AAPL, ^GSPC ... (recommended for mixing)
      binance        Binance spot (USDT pairs only): BTCUSDT, ETHUSDT
      binancefutures Binance COIN-M futures (USD): BTCUSD_PERP, ETHUSD_PERP
      bybit          Bybit spot (USDT pairs): BTCUSDT
    """
    tf = timeframe.lower()

    if exchange == "yahoo":
        yint = YAHOO_INT.get(tf)
        if not yint:
            raise ValueError(f"Yahoo source doesn't support timeframe '{timeframe}' (use 1m/5m/15m/30m/1h/1d)")
        yrange = "2y" if tf == "1d" else "60d"
        sym_enc = urllib.parse.quote(symbol, safe="")
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_enc}"
               f"?interval={yint}&range={yrange}")
        res = _http_get_json(url)["chart"]["result"][0]
        ts = res.get("timestamp", []) or []
        q = res["indicators"]["quote"][0]
        out = []
        for i in range(len(ts)):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c):
                continue
            out.append({"t": int(ts[i]) * 1000, "o": float(o), "h": float(h),
                        "l": float(l), "c": float(c)})
        return out[:-1] if out else out

    if tf not in TF_MIN:
        raise ValueError(f"Unsupported TIMEFRAME '{timeframe}'")

    if exchange == "binance":
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
               f"&interval={tf}&limit={limit}")
        rows = _http_get_json(url)
        out = [{"t": int(r[0]), "o": float(r[1]), "h": float(r[2]),
                "l": float(r[3]), "c": float(r[4])} for r in rows]
    elif exchange == "binancefutures":  # COIN-M (USD): BTCUSD_PERP etc.
        url = (f"https://dapi.binance.com/dapi/v1/klines?symbol={symbol}"
               f"&interval={tf}&limit={min(limit, 1500)}")
        rows = _http_get_json(url)
        out = [{"t": int(r[0]), "o": float(r[1]), "h": float(r[2]),
                "l": float(r[3]), "c": float(r[4])} for r in rows]
    else:  # bybit spot
        minutes = TF_MIN[tf]
        bb_int = "D" if minutes == 1440 else str(minutes)
        url = (f"https://api.bybit.com/v5/market/kline?category=spot"
               f"&symbol={symbol}&interval={bb_int}&limit={limit}")
        data = _http_get_json(url)
        rows = list(reversed(data.get("result", {}).get("list", [])))  # newest-first
        out = [{"t": int(r[0]), "o": float(r[1]), "h": float(r[2]),
                "l": float(r[3]), "c": float(r[4])} for r in rows]

    return out[:-1] if out else out  # drop in-progress candle


# ── Rolling helpers ──────────────────────────────────────────────────────────
def lowest(lows, i, length):
    return min(lows[i - length + 1: i + 1])


def highest(highs, i, length):
    return max(highs[i - length + 1: i + 1])


def donchian(highs, lows, i, length):
    return (lowest(lows, i, length) + highest(highs, i, length)) / 2.0


def compute_signals(candles, pos_size):
    """Replay the full series deterministically (mirrors Pine's var state) and
    return, per bar index, a signal dict or None."""
    n = len(candles)
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]

    conv = [None] * n
    base = [None] * n
    lead1 = [None] * n
    lead2 = [None] * n
    for i in range(n):
        if i >= CONV_PERIODS - 1:
            conv[i] = donchian(highs, lows, i, CONV_PERIODS)
        if i >= BASE_PERIODS - 1:
            base[i] = donchian(highs, lows, i, BASE_PERIODS)
        if conv[i] is not None and base[i] is not None:
            lead1[i] = (conv[i] + base[i]) / 2.0
        if i >= LEAD2_PERIODS - 1:
            lead2[i] = donchian(highs, lows, i, LEAD2_PERIODS)

    signals = [None] * n

    pos = 0
    stop = None
    entry = None
    last_exit_bar = -99999

    start = 2 * D + LEAD2_PERIODS  # warmup so displaced lead2[i-2d] is valid
    for i in range(start, n):
        close = closes[i]

        cloud_top = max(lead1[i - D], lead2[i - D])
        cloud_bot = min(lead1[i - D], lead2[i - D])
        lag_top = max(lead1[i - 2 * D], lead2[i - 2 * D])
        lag_bot = min(lead1[i - 2 * D], lead2[i - 2 * D])

        kumo_ok = (not USE_KUMO_THK) or (cloud_top - cloud_bot) / close * 100 >= KUMO_MIN_PCT
        tk_ok = (not USE_TK_SEP) or abs(conv[i] - base[i]) / close * 100 >= TK_MIN_PCT
        kj_up = (not USE_KJ_SLOPE) or base[i] > base[i - KJ_SLOPE_LEN]
        kj_down = (not USE_KJ_SLOPE) or base[i] < base[i - KJ_SLOPE_LEN]
        chikou_up_ok = (not USE_CHIKOU_OS) or close > highest(highs, i - D, 5)
        chikou_down_ok = (not USE_CHIKOU_OS) or close < lowest(lows, i - D, 5)

        long_setup = (close > cloud_top and lead1[i] > lead2[i]
                      and conv[i] > base[i] and close > lag_top
                      and kj_up and kumo_ok and tk_ok and chikou_up_ok)
        short_setup = (close < cloud_bot and lead1[i] < lead2[i]
                       and conv[i] < base[i] and close < lag_bot
                       and kj_down and kumo_ok and tk_ok and chikou_down_ok)

        # Chikou (close) x Tenkan (conv displaced) crosses
        lag_cross_down = close < conv[i - D] and closes[i - 1] >= conv[i - 1 - D]
        lag_cross_up = close > conv[i - D] and closes[i - 1] <= conv[i - 1 - D]

        # Exit priority: SL > Chikou cross  (same order as Pine)
        sl_hit = (pos == 1 and lows[i] <= stop) or (pos == -1 and highs[i] >= stop)
        lag_x = (not sl_hit) and ((pos == 1 and lag_cross_down) or (pos == -1 and lag_cross_up))
        exit_sig = sl_hit or lag_x
        was_long = pos == 1

        if exit_sig:
            exit_price = stop if sl_hit else close
            pnl = (exit_price - entry if was_long else entry - exit_price) * pos_size
            signals[i] = {
                "signal": "EXIT_SL" if sl_hit else "EXIT",
                "price": exit_price,
                "pnl": int(round(pnl)),
                "side": "LONG" if was_long else "SHORT",
            }
            pos = 0
            stop = None
            entry = None
            last_exit_bar = i

        cooldown_ok = i - last_exit_bar > COOLDOWN
        long_sig = (not exit_sig) and pos == 0 and cooldown_ok and long_setup
        short_sig = (not exit_sig) and pos == 0 and cooldown_ok and short_setup

        if long_sig:
            pos = 1
            stop = cloud_bot
            entry = close
            signals[i] = {"signal": "LONG", "price": close, "stop": stop}
        elif short_sig:
            pos = -1
            stop = cloud_top
            entry = close
            signals[i] = {"signal": "SHORT", "price": close, "stop": stop}

    return signals


# ── Messaging ────────────────────────────────────────────────────────────────
def fmt_num(v):
    if not isinstance(v, float):
        return f"{v:,}"
    a = abs(v)
    dec = 2 if a >= 100 else 4 if a >= 1 else 6  # forex/low-price get more decimals
    return f"{v:,.{dec}f}".rstrip("0").rstrip(".")


def format_message(symbol, timeframe, sig):
    icon = {"LONG": "🟢", "SHORT": "🔴", "EXIT_SL": "🛑", "EXIT": "⚪"}.get(sig["signal"], "🔔")
    lines = [f"{icon} *Ichimoku {sig['signal']}*", f"{symbol}  ·  {timeframe}"]
    if "price" in sig:
        lines.append(f"Price: {fmt_num(sig['price'])}")
    if "stop" in sig:
        lines.append(f"Stop: {fmt_num(sig['stop'])}")
    if "pnl" in sig:
        sign = "+" if sig["pnl"] >= 0 else ""
        lines.append(f"P&L: {sign}{fmt_num(sig['pnl'])} USD  ({sig.get('side','')})")
    return "\n".join(lines)


def send_message(text):
    """Send to the configured destination.

    PROVIDER=telegram  (free, official Bot API, recommended) -> TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    PROVIDER=whapi / wassenger (WhatsApp gateways)           -> WA_TOKEN, WA_GROUP_ID
    """
    if env("DRY_RUN") == "1":
        # Write UTF-8 bytes directly so emoji don't crash limited consoles (Windows cp1252).
        sys.stdout.buffer.write(("[DRY_RUN] would send:\n" + text + "\n\n").encode("utf-8"))
        sys.stdout.flush()
        return

    provider = (env("PROVIDER") or env("WA_PROVIDER", "telegram")).lower()

    if provider == "telegram":
        token = env("TELEGRAM_BOT_TOKEN")
        chat_id = env("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        headers = {"Content-Type": "application/json"}
        body = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    else:
        token = env("WA_TOKEN")
        group = env("WA_GROUP_ID")
        if not token or not group:
            raise RuntimeError("WA_TOKEN and WA_GROUP_ID must be set")
        if provider == "wassenger":
            url = "https://api.wassenger.com/v1/messages"
            headers = {"Token": token, "Content-Type": "application/json"}
            body = {"group": group, "message": text}
        else:  # whapi
            url = "https://gate.whapi.cloud/messages/text"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            body = {"to": group, "body": text}

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


# Backwards-compatible alias
send_whatsapp = send_message


# ── State (dedupe by last-processed candle open time, per symbol) ─────────────
def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


# ── Main ─────────────────────────────────────────────────────────────────────
def parse_specs():
    """Each SYMBOLS entry is `symbol[:timeframe[:exchange]]`; missing parts fall
    back to the global TIMEFRAME / EXCHANGE. Lets BTC run on 4h while others differ.
    e.g. SYMBOLS="BTCUSD_PERP:4h:binancefutures,ETH-USD:1d:yahoo"
    """
    default_tf = env("TIMEFRAME", "1h").lower()
    default_ex = env("EXCHANGE", "yahoo").lower()
    specs = []
    for raw in env("SYMBOLS", "BTCUSD_PERP:4h:binancefutures").split(","):
        raw = raw.strip()
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(":")]
        sym = parts[0]
        tf = parts[1].lower() if len(parts) > 1 and parts[1] else default_tf
        ex = parts[2].lower() if len(parts) > 2 and parts[2] else default_ex
        specs.append((sym, tf, ex))
    return specs


def main():
    pos_size = float(env("POS_SIZE", "1"))
    state_path = env("STATE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"))

    state = load_state(state_path)
    sent_any = False

    for symbol, timeframe, exchange in parse_specs():
        try:
            candles = fetch_candles(symbol, timeframe, exchange)
        except (urllib.error.URLError, ValueError, KeyError, IndexError) as e:
            print(f"[{symbol} {timeframe} {exchange}] fetch error: {e}", file=sys.stderr)
            continue

        if len(candles) < 2 * D + LEAD2_PERIODS + 5:
            print(f"[{symbol}] not enough candles ({len(candles)})", file=sys.stderr)
            continue

        signals = compute_signals(candles, pos_size)
        key = f"{exchange}:{symbol}:{timeframe}"
        last_processed = state.get(key)
        latest_closed_t = candles[-1]["t"]

        if last_processed is None:
            # First run for this symbol: initialize silently to avoid dumping
            # a backlog of historical signals.
            state[key] = latest_closed_t
            print(f"[{key}] initialized at {latest_closed_t} (no backlog sent)")
            continue

        # Send any signal on bars newer than the last processed one (catch-up).
        new_signals = [(candles[i]["t"], signals[i])
                       for i in range(len(candles))
                       if signals[i] is not None and candles[i]["t"] > last_processed]
        for t, sig in new_signals:
            send_message(format_message(symbol, timeframe, sig))
            sent_any = True
            print(f"[{key}] sent {sig['signal']} @ {t}")

        state[key] = latest_closed_t

    save_state(state_path, state)
    if not sent_any:
        print("No new signals.")


if __name__ == "__main__":
    main()
