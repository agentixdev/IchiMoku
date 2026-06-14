// Vercel serverless function: relays TradingView alerts to a WhatsApp group.
//
// Flow:  TradingView alert (webhook)  ->  this function  ->  WhatsApp gateway  ->  "Ichimoku" group
//
// The Pine Script sends a JSON body like:
//   {"group":"Ichimoku","signal":"LONG","ticker":"BTCUSDT","tf":"60","price":64210.5,"stop":63500}
//   {"group":"Ichimoku","signal":"EXIT_SL","ticker":"BTCUSDT","tf":"60","price":63500,"pnl":-710,"side":"LONG"}
//
// Required environment variables (set in Vercel project settings):
//   WEBHOOK_SECRET   shared secret; TradingView URL must include ?token=<this>
//   WA_PROVIDER      "whapi" (default) or "wassenger"
//   WA_TOKEN         API token from your WhatsApp gateway
//   WA_GROUP_ID      the WhatsApp group id, e.g. 120363XXXXXXXXXXXX@g.us

const PROVIDERS = {
  // https://whapi.cloud  ->  Channels -> your channel -> API token
  whapi: {
    url: 'https://gate.whapi.cloud/messages/text',
    headers: (token) => ({
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }),
    body: (groupId, text) => ({ to: groupId, body: text }),
  },
  // https://wassenger.com  ->  Devices -> API -> create token
  wassenger: {
    url: 'https://api.wassenger.com/v1/messages',
    headers: (token) => ({ Token: token, 'Content-Type': 'application/json' }),
    body: (groupId, text) => ({ group: groupId, message: text }),
  },
};

async function readRawBody(req) {
  if (typeof req.body === 'string') return req.body;
  if (req.body && typeof req.body === 'object') return JSON.stringify(req.body);
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

function num(v) {
  return typeof v === 'number' ? v.toLocaleString('en-US') : v;
}

// Turn the indicator's JSON (or plain text) into a readable WhatsApp message.
function formatMessage(payload) {
  if (typeof payload === 'string') return `📈 Ichimoku\n${payload}`;

  const { signal = 'SIGNAL', ticker = '?', tf = '?', price, stop, pnl, side } = payload;
  const icon =
    signal === 'LONG' ? '🟢' :
    signal === 'SHORT' ? '🔴' :
    signal === 'EXIT_SL' ? '🛑' :
    signal === 'EXIT' ? '⚪' : '🔔';

  const lines = [`${icon} *Ichimoku ${signal}*`, `${ticker}  ·  ${tf}`];
  if (price != null) lines.push(`Price: ${num(price)}`);
  if (stop != null) lines.push(`Stop: ${num(stop)}`);
  if (pnl != null) {
    const sign = pnl >= 0 ? '+' : '';
    lines.push(`P&L: ${sign}${num(pnl)} USD${side ? `  (${side})` : ''}`);
  }
  return lines.join('\n');
}

export default async function handler(req, res) {
  if (req.method === 'GET') {
    return res.status(200).json({ ok: true, service: 'ichimoku-whatsapp-relay' });
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'method_not_allowed' });
  }

  // Auth — TradingView appends ?token=... to the webhook URL.
  const secret = process.env.WEBHOOK_SECRET;
  if (!secret || req.query.token !== secret) {
    return res.status(401).json({ error: 'unauthorized' });
  }

  const provider = PROVIDERS[process.env.WA_PROVIDER || 'whapi'];
  const token = process.env.WA_TOKEN;
  const groupId = process.env.WA_GROUP_ID;
  if (!provider || !token || !groupId) {
    return res.status(500).json({ error: 'relay_not_configured' });
  }

  let payload;
  try {
    const raw = await readRawBody(req);
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = raw; // not JSON — forward as plain text
    }
  } catch {
    return res.status(400).json({ error: 'bad_body' });
  }

  const text = formatMessage(payload);

  try {
    const resp = await fetch(provider.url, {
      method: 'POST',
      headers: provider.headers(token),
      body: JSON.stringify(provider.body(groupId, text)),
    });
    const data = await resp.text();
    if (!resp.ok) {
      console.error('gateway_error', resp.status, data);
      return res.status(502).json({ error: 'gateway_error', status: resp.status, detail: data });
    }
    return res.status(200).json({ ok: true, sent: text });
  } catch (err) {
    console.error('relay_failed', err);
    return res.status(502).json({ error: 'relay_failed', detail: String(err) });
  }
}
