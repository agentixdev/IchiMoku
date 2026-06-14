# Ichimoku → WhatsApp alerts

Sends your **Ichimoku Signals Final** indicator's signals (LONG / SHORT / EXIT) into a
WhatsApp group called **Ichimoku**.

There are **two ways** to do this. Pick one:

| | Path A — Signal engine (recommended) | Path B — TradingView webhook |
|---|---|---|
| TradingView plan | **Free** ✅ | **Paid** (Essential+) |
| How it works | Recomputes the indicator from free exchange candles on a schedule | TradingView fires a webhook to a relay |
| Runs when you're offline | Yes (VPS cron) | Yes (TradingView servers) |
| Exact indicator parity | Yes (full logic ported) | Yes (native) |
| Market | Crypto (Bybit/Binance) | Anything on TradingView |

### Destination: Telegram (free, recommended) or WhatsApp (paid-ish)
- **Telegram** — *completely free*, official Bot API, sends to groups directly. No gateway,
  no monthly fee, no QR, no linked phone. **Recommended.** Set `PROVIDER=telegram`.
- **WhatsApp** — needs a third-party gateway (Whapi.cloud free Sandbox, or Wassenger trial)
  because WhatsApp has **no official group-send API**. Set `PROVIDER=whapi`/`wassenger`.

#### Telegram setup (2 minutes)
1. In Telegram, message **@BotFather** → `/newbot` → follow prompts → copy the **bot token**
   (looks like `123456:ABC...`).
2. Create/open your **Ichimoku** group, **add your bot** to it (and make it admin so it can
   post). Send any message in the group.
3. Get the group **chat id** — run:
   ```bash
   curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates" | python -m json.tool
   ```
   Find `"chat": {"id": -100...}` — that negative number is your `TELEGRAM_CHAT_ID`.
4. Put `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` into `run.sh`.

> ### ❌ What does NOT work — and why
> - **The `tradingview-mcp-server` MCP** is a market *screener*. It cannot create alerts,
>   cannot take screenshots, and cannot send WhatsApp messages. It's only useful for ad-hoc
>   scans. (A schedulable digest version is included below — but it computes from candles,
>   not from the MCP, because MCP tools only run inside a live Claude session.)
> - **Screenshotting your TradingView chart to read the badges.** Your chart layout is
>   *private to your account*, so an automated browser hits a login wall ("If you're the
>   owner of this chart, log in to see it"). Even with your login, nothing runs unattended
>   without a scheduler, and reading badges from an image is unreliable. **Path A replaces
>   this entirely** — it reproduces the badges' logic from data, no chart needed.

---

## Path A — Signal engine (no TradingView subscription)

Located in [`signal-engine/`](signal-engine/). Pure Python standard library (no pip).
It pulls free OHLC candles, replays your indicator's exact logic (cloud, Chikou, chop
filters, stateful entries, fixed-SL exits, Chikou-cross exits, cooldown), and sends any
**new** signal to WhatsApp. State is deduped so you never get the same alert twice.

### 1. Pick a destination (one-time)
See **"Destination"** above. Telegram (free) is recommended — get a bot token + chat id.
WhatsApp works too via a gateway if you prefer that app.

### 2. Put it on your Hostinger VPS
```bash
scp -r signal-engine youruser@your-vps:/opt/ichimoku
ssh youruser@your-vps
cd /opt/ichimoku
# edit run.sh: set WA_TOKEN, WA_GROUP_ID, SYMBOLS, TIMEFRAME, EXCHANGE
chmod +x run.sh
DRY_RUN=1 ./run.sh        # test: prints what it WOULD send, sends nothing
```
First real run per symbol initializes silently (no backlog spam); subsequent runs send
new signals only.

### 3. Schedule it (cron)
Match the cron frequency to your timeframe. Example for a 1h timeframe, run a few minutes
after each hour close:
```cron
# crontab -e
5 * * * * /opt/ichimoku/run.sh
```
For 15m: `*/15 * * * *`. For 1d: `10 0 * * *`.

### Config (env vars, set in `run.sh`)
| var | default | meaning |
|---|---|---|
| `SYMBOLS` | `BTCUSDT,ETHUSDT` | comma list of pairs |
| `TIMEFRAME` | `1h` | `1m,5m,15m,30m,1h,2h,4h,6h,12h,1d` |
| `EXCHANGE` | `bybit` | `bybit` (broad access incl. US) or `binance` |
| `PROVIDER` | `telegram` | `telegram` (free), `whapi`, or `wassenger` |
| `TELEGRAM_BOT_TOKEN` | — | from @BotFather (if telegram) |
| `TELEGRAM_CHAT_ID` | — | group chat id, e.g. `-1001234567890` (if telegram) |
| `WA_TOKEN` | — | gateway token (if whapi/wassenger) |
| `WA_GROUP_ID` | — | `...@g.us` (if whapi/wassenger) |
| `POS_SIZE` | `1` | units for P&L on exits |
| `DRY_RUN` | — | `1` = print instead of send |

### Complementary digest (the "screener" view)
[`signal-engine/digest.py`](signal-engine/digest.py) scans a watchlist and reports each
symbol's current Ichimoku bias (bullish / bearish / in-cloud). Schedule it once or twice a
day for an overview:
```cron
0 8 * * * cd /opt/ichimoku && WATCHLIST="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT" TIMEFRAME=4h ./run-digest.sh
```

---

## Path B — TradingView webhook relay (needs a paid plan)

A Vercel function (`api/tradingview-webhook.js`) receives TradingView alerts and forwards
them to the gateway. Use this only if you have TradingView Essential+ (webhooks aren't on
Free). The indicator already emits JSON via `alert()`.

1. Deploy: `vercel` then `vercel --prod`; set env vars `WEBHOOK_SECRET`, `WA_PROVIDER`,
   `WA_TOKEN`, `WA_GROUP_ID`.
2. In TradingView: Create Alert → condition **"Any alert() function call"** → *Once Per
   Bar Close* → Webhook URL:
   `https://YOUR-PROJECT.vercel.app/api/tradingview-webhook?token=YOUR_WEBHOOK_SECRET`

Test:
```bash
curl -X POST "https://YOUR-PROJECT.vercel.app/api/tradingview-webhook?token=YOUR_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"group":"Ichimoku","signal":"LONG","ticker":"BTCUSDT","tf":"60","price":64210.5,"stop":63500}'
```

---

## Repo layout
```
indicator/Ichimoku_Signals_Final.pine   the Pine v6 indicator (now emits alert() JSON)
signal-engine/ichimoku_engine.py        Path A: signal engine (no premium)
signal-engine/digest.py                 Path A: screener digest
signal-engine/run.sh                    cron wrapper
api/tradingview-webhook.js              Path B: Vercel webhook relay
vercel.json, package.json, .env.example Path B config
```

## Notes / limits
- Gateways automate WhatsApp Web; keep the linked phone online. Fine for personal,
  low-volume alerts; high-volume/spam use violates WhatsApp's ToS.
- A WhatsApp message produced by the engine looks like:
  ```
  🟢 *Ichimoku LONG*
  BTCUSDT  ·  1h
  Price: 64,210.5
  Stop: 63,500
  ```
