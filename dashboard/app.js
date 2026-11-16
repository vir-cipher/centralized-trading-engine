/*
  Dashboard logic.

  In plain words:
    Every 3 seconds: ask the API for candles, the latest price, the advice,
    recent deals and our orders, then redraw. All the thinking happens on the
    server; this file only fetches and draws.

    The two averages are re-computed here only to draw the lines. The advice
    itself comes from the server (/signals), so the screen and the API can
    never disagree.
*/
const SYMBOL = "BTCUSDT", SHORT = 5, LONG = 15;
let API = "", SNAPSHOT = null, chart = null;

// --- small helpers ---
const $ = (id) => document.getElementById(id);
const fmt = (n, d = 2) => (n == null ? "–" : Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
const utc = (ms) => new Date(ms).toISOString().slice(11, 19);

// Moving average of the last n values at every point (null until there are n values).
function smaSeries(values, n) {
  return values.map((_, i) => (i + 1 < n ? null : values.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
}

// Where does the short line cross the long one? Returns [{i, kind: "BUY"|"SELL"}].
function crossings(s, l) {
  const out = [];
  for (let i = 1; i < s.length; i++) {
    if (s[i - 1] == null || l[i - 1] == null) continue;
    if (s[i - 1] <= l[i - 1] && s[i] > l[i]) out.push({ i, kind: "BUY" });
    if (s[i - 1] >= l[i - 1] && s[i] < l[i]) out.push({ i, kind: "SELL" });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Call trace: the black "terminal" box under the chart.
//
// In plain words:
//   Every time this page talks to our API, we write one line like a terminal:
//       $ curl -s http://localhost:8000/prices/BTCUSDT
//       <- 200 OK  12 ms  {"symbol":"BTCUSDT","price":...}
//   So you can SEE each call happen, copy it, and run the same call yourself
//   in a real terminal (or in Postman). The secret key is never shown: it is
//   printed as ****.
// ---------------------------------------------------------------------------
const TRACE_MAX = 80;          // keep only the newest 80 lines on screen
let tracePaused = false, refreshNo = 0, lastCurl = "";

// What base address to print in the curl line.
function baseUrl() {
  return SNAPSHOT ? "http://localhost:8000" : (API || location.origin);
}

// Turn one call into the curl command that does the same thing.
function asCurl(method, path, body, withKey) {
  let c = "curl -s";
  if (method !== "GET") c += " -X " + method;
  if (withKey) c += " -H 'X-API-Key: ****'";
  if (body) c += " -H 'Content-Type: application/json' -d '" + JSON.stringify(body) + "'";
  return c + " '" + baseUrl() + path + "'";
}

// Write lines into the black box. kind = "cmd" | "ok" | "err" | "meta".
function traceLine(kind, text, boxId = "trace") {
  if (tracePaused) return;
  const box = $(boxId);
  if (!box) return;
  const line = document.createElement("div");
  // Anything about orders (our POST/DELETE, Binance, the pretend exchange) gets its own colour.
  const isOrder = /\/orders(\/|'|\s|$)|-X (POST|DELETE)|Binance (POST|DELETE)|pretend exchange|<- Binance/.test(text) && !/^\S+\s+\$ curl -s '[^']*\/orders'$/.test(text) && !/GET\s+\/orders/.test(text);
  line.className = "t-" + kind + (isOrder ? " t-order" : "");
  line.textContent = text;
  box.appendChild(line);
  while (box.children.length > TRACE_MAX) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}

// Short preview of an answer, so one call stays on one or two lines.
function preview(data) {
  const s = JSON.stringify(data);
  if (s === undefined) return "";
  return s.length > 90 ? s.slice(0, 90) + " ..." : s;
}

// One call to our API, with its trace lines. Every request goes through here.
async function callApi(method, path, body, key) {
  const t0 = performance.now();
  const clock = new Date().toTimeString().slice(0, 8);
  const cmd = asCurl(method, path, body, Boolean(key));
  lastCurl = cmd;
  // Several calls run at the same time, so the command and its answer are
  // written together when the answer arrives; otherwise the lines would mix.
  if (SNAPSHOT) {                                   // static website: read the recorded answer
    const data = SNAPSHOT[path];
    traceLine("cmd", clock + "  $ " + cmd);
    traceLine("ok", "          <- 200 (recorded in snapshot.json)  " + preview(data));
    return { ok: true, status: 200, data };
  }
  const headers = {};
  if (key) headers["X-API-Key"] = key;
  if (body) headers["Content-Type"] = "application/json";
  try {
    const r = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = await r.json();
    const ms = Math.round(performance.now() - t0);
    traceLine("cmd", clock + "  $ " + cmd);
    traceLine(r.ok ? "ok" : "err", "          <- " + r.status + " " + (r.ok ? "OK" : "ERROR") + "  " + ms + " ms  " + preview(data));
    return { ok: r.ok, status: r.status, data };
  } catch (e) {
    traceLine("cmd", clock + "  $ " + cmd);
    traceLine("err", "          <- no answer (is the engine running?)  " + e.message);
    throw e;
  }
}

// Ask the API (GET), or read the snapshot if we are on a static website.
async function get(path) {
  const r = await callApi("GET", path);
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.data;
}

function drawChart(candles) {
  const closes = candles.map((c) => c.close), labels = candles.map((c) => utc(c.minute_start_ms).slice(0, 5));
  const s = smaSeries(closes, SHORT), l = smaSeries(closes, LONG), marks = crossings(s, l);
  const ink = getComputedStyle(document.documentElement).getPropertyValue("--ink").trim();
  const muted = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim();
  const data = {
    labels,
    datasets: [
      { label: "price", data: closes, borderColor: muted, borderWidth: 1.2, pointRadius: 0 },
      { label: SHORT + "-minute average", data: s, borderColor: ink, borderDash: [6, 4], borderWidth: 2, pointRadius: 0 },
      { label: LONG + "-minute average", data: l, borderColor: ink, borderWidth: 4, pointRadius: 0 },
    ],
  };
  // The BUY/SELL words drawn on the chart (a tiny Chart.js plugin).
  const words = {
    id: "words",
    afterDatasetsDraw(c) {
      const ctx = c.ctx, x = c.scales.x, y = c.scales.y;
      ctx.save(); ctx.font = "bold 13px system-ui"; ctx.fillStyle = ink; ctx.textAlign = "center";
      marks.forEach((m) => {
        const px = x.getPixelForValue(m.i), py = y.getPixelForValue(l[m.i]);
        ctx.fillText(m.kind === "BUY" ? "▲ BUY" : "▼ SELL", px, m.kind === "BUY" ? py + 22 : py - 12);
      });
      ctx.restore();
    },
  };
  if (chart) { chart.data = data; chart.update("none"); return; }
  chart = new Chart($("chart"), {
    type: "line", data, plugins: [words],
    options: { animation: false, maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 8, color: muted } }, y: { ticks: { color: muted } } } },
  });
}

async function refresh() {
  refreshNo += 1;
  traceLine("meta", "---- refresh #" + refreshNo + " ----");
  try {
    const [candles, price, sig, trades, orders, health] = await Promise.all([
      get("/candles?symbol=" + SYMBOL + "&limit=120"), get("/prices/" + SYMBOL), get("/signals/" + SYMBOL),
      get("/trades?symbol=" + SYMBOL + "&limit=12"), get("/orders"), get("/health"),
    ]);
    const mode = SNAPSHOT ? "SNAPSHOT" : health.mode;
    $("badge").textContent = mode; $("badge").className = "badge " + mode.toLowerCase();
    $("price").textContent = fmt(price.price) + " USDT";
    drawChart(candles);
    const arrow = { BUY: "▲ BUY", SELL: "▼ SELL", HOLD: "■ HOLD" }[sig.advice];
    $("advice").textContent = arrow;
    currentAdvice = sig.advice;
    $("follow-advice").disabled = SNAPSHOT || sig.advice === "HOLD";
    $("follow-advice").textContent = sig.advice === "HOLD" ? "Follow advice (HOLD: nothing to do)" : "Follow advice: " + sig.advice;
    $("reason").textContent = sig.reason + " (advice only)";
    const h = sig.honest_test;
    $("honest").textContent = h.rule_accuracy == null ? h.note
      : `Honest test on ${h.scored_minutes} later minutes: rule ${Math.round(h.rule_accuracy * 100)}% vs always-guess-the-commonest ${Math.round(h.baseline_accuracy * 100)}%`;
    $("trades").innerHTML = trades.map((t) => `<tr><td>${utc(t.ts)}</td><td>${fmt(t.price)}</td><td>${t.qty}</td></tr>`).join("");
    $("orders").innerHTML = orders.map((o) =>
      `<tr><td>${o.id}</td><td>${o.side === "BUY" ? "▲ BUY" : "▼ SELL"}</td><td>${o.type}</td><td>${o.qty}</td>` +
      `<td>${fmt(o.filled_price ?? o.price)}</td><td>${costText(o)}</td><td>${o.status}</td>` +
      `<td>${o.note === "SIMULATED" ? "pretend exchange" : "Binance Testnet"}</td>` +
      `<td>${o.status === "NEW" && !SNAPSHOT ? `<button type="button" data-cancel="${o.id}">Cancel</button>` : ""}</td></tr>`).join("");
    showInventory(orders);
    showPortfolio(orders, price.price);
    announceFills(orders);
    explainSource(mode);
  } catch (e) {
    $("badge").textContent = "OFFLINE"; $("badge").className = "badge";
  }
}

// ---------------------------------------------------------------------------
// Cost of one order: quantity x price. BUY = money goes out (-), SELL = money comes in (+).
// ---------------------------------------------------------------------------
function costText(o) {
  const p = o.filled_price ?? o.price;
  if (p == null) return "–";
  const cost = o.qty * p;
  return (o.side === "BUY" ? "− " : "+ ") + fmt(cost) + " USDT";
}

// ---------------------------------------------------------------------------
// Profit or loss, worked out from the order list only.
//
// In plain words:
//   Add up every FILLED order: how much BTC we bought (minus what we sold),
//   and how much cash we spent (minus what we got back). What that BTC is
//   worth at today's price, minus the cash we spent, is our gain or loss.
//   The order history is our ledger; nothing else is stored.
// ---------------------------------------------------------------------------
function showPortfolio(orders, priceNow) {
  const filled = orders.filter((o) => o.status === "FILLED" && o.filled_price);
  let btc = 0, cash = 0;
  for (const o of filled) {
    const amount = o.qty * o.filled_price;
    if (o.side === "BUY") { btc += o.qty; cash -= amount; } else { btc -= o.qty; cash += amount; }
  }
  const valueNow = btc * priceNow;
  const pnl = valueNow + cash;            // what we hold now + cash we got back - cash we paid
  const where = filled.some((o) => o.note !== "SIMULATED") ? "Binance Testnet orders (toy money)" : "SIMULATED orders (pretend exchange)";
  $("pf-source").textContent = filled.length ? `From ${filled.length} filled orders · ${where}` : "No filled orders yet: place one to see the gain or loss.";
  $("pf-btc").textContent = btc.toFixed(6) + " BTC";
  $("pf-cash").textContent = (cash <= 0 ? "spent " : "received ") + fmt(Math.abs(cash)) + " USDT";
  $("pf-value").textContent = fmt(valueNow) + " USDT";
  $("pf-pnl").textContent = (pnl >= 0 ? "▲ gain " : "▼ loss ") + fmt(Math.abs(pnl)) + " USDT";
  $("pf-pnl").className = "pnl " + (pnl >= 0 ? "up" : "down");
}

// "Follow advice": copy the advice (BUY or SELL) into the order form. A human still presses Send.
let currentAdvice = "HOLD";
$("follow-advice").addEventListener("click", () => {
  if (currentAdvice === "HOLD") return;
  $("order").elements.side.value = currentAdvice;
  $("order").elements.type.value = "MARKET";
  $("order-msg").textContent = "Form filled from the advice: " + currentAdvice + " MARKET. Check the quantity, then press Send order.";
});

// ---------------------------------------------------------------------------
// Inventory: what we hold now, and how many orders are open / filled / cancelled.
// ---------------------------------------------------------------------------
async function showInventory(orders) {
  const count = (st) => orders.filter((o) => o.status === st).length;
  $("inv-counts").textContent =
    `Orders: ${orders.length} in total · ${count("FILLED")} filled · ${count("NEW")} open · ${count("CANCELED")} cancelled`;
  if (SNAPSHOT) { $("inv-balances").innerHTML = '<tr><td colspan="3">Balances need a running engine.</td></tr>'; return; }
  try {
    const bal = await get("/account/balance");
    $("inv-balances").innerHTML = bal.map((b) =>
      `<tr><td>${b.asset}</td><td>${fmt(b.free, b.asset === "USDT" ? 2 : 6)}</td><td>${fmt(b.locked, b.asset === "USDT" ? 2 : 6)}</td></tr>`).join("");
  } catch (e) {
    $("inv-balances").innerHTML = '<tr><td colspan="3">No balances: the engine has no exchange keys (orders are switched off).</td></tr>';
  }
}

// Pop-up when an order becomes FILLED. We remember each order's last status;
// a change to FILLED (or a brand-new order that is already FILLED) gets a pop-up.
let lastStatus = null;           // null = first look, so old orders do not pop up
function announceFills(orders) {
  const now = {};
  for (const o of orders) {
    now[o.id] = o.status;
    const before = lastStatus ? lastStatus[o.id] : "FILLED";
    if (o.status === "FILLED" && before !== "FILLED") {
      const where = o.note === "SIMULATED" ? "pretend exchange (SIMULATED)" : "Binance Testnet";
      popup(`✅ Order ${o.id} FILLED: ${o.side} ${o.qty} ${o.symbol}` +
            (o.filled_price ? ` at ${fmt(o.filled_price)} USDT` : "") + ` · ${where}`);
    }
  }
  lastStatus = now;
}

// A small box in the corner that fades away by itself (no blocking alert).
function popup(text) {
  const box = document.createElement("div");
  box.className = "toast"; box.setAttribute("role", "status"); box.textContent = text;
  $("toasts").appendChild(box);
  setTimeout(() => box.classList.add("gone"), 6000);
  setTimeout(() => box.remove(), 6800);
}

// Real feed or simulated? One plain sentence for each mode.
function explainSource(mode) {
  const text = {
    LIVE: "LIVE: prices are the real Binance Spot Testnet trade stream, arriving now. Orders are really sent to Binance Testnet (practice market, toy money), signed with our secret key.",
    REPLAY: "REPLAY: prices are REAL Testnet trades that were recorded earlier and are now played back in a loop, so the demo works without internet. Orders go to a pretend exchange inside the engine and are marked SIMULATED.",
    SNAPSHOT: "SNAPSHOT: this is a static website. Everything shown is one recorded moment (snapshot.json); nothing moves and orders are switched off. Run the engine on a laptop for the real thing.",
  }[mode] || "The engine says it is in " + mode + " mode.";
  $("source-note").textContent = text;
}

// Place an order through our own API (needs the plugin key).
$("order").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (SNAPSHOT) { $("order-msg").textContent = "This is a static snapshot: orders work only when the engine runs on the laptop."; return; }
  const f = new FormData(ev.target), body = { symbol: SYMBOL, side: f.get("side"), type: f.get("type"), qty: Number(f.get("qty")) };
  if (body.type === "LIMIT") body.price = Number(f.get("price"));
  const r = await callApi("POST", "/orders", body, f.get("key"));
  const j = r.data;
  $("order-msg").textContent = r.ok ? `Order ${j.id}: ${j.status}${j.filled_price ? " at " + fmt(j.filled_price) : ""}` : `Refused: ${j.error.code} (${j.error.message})`;
  refresh();
});

document.addEventListener("click", async (ev) => {
  const id = ev.target.getAttribute && ev.target.getAttribute("data-cancel");
  if (!id) return;
  const key = new FormData($("order")).get("key");
  const r = await callApi("DELETE", "/orders/" + id, null, key);
  const j = r.data;
  $("order-msg").textContent = r.ok ? `Order ${id}: ${j.status}` : `Refused: ${j.error.code}`;
  refresh();
});

// The engine's own log (GET /trace): what the ENGINE saw, including its calls to Binance.
let engineAfter = 0;
async function pollEngineLog() {
  if (SNAPSHOT || tracePaused) return;
  try {
    const r = await fetch(API + "/trace?after=" + engineAfter);
    if (!r.ok) return;
    for (const x of await r.json()) {
      engineAfter = x.id;
      traceLine(x.kind === "out" ? "ok" : x.kind === "in" ? "cmd" : "meta", x.t + "  " + x.text, "engine-log");
    }
  } catch (e) { /* engine stopped; the page trace already says so */ }
}

// Two views of the same black box: what this page sent, and what the engine logged.
function showView(which) {
  const engine = which === "engine";
  $("trace").hidden = engine; $("engine-log").hidden = !engine;
  $("view-page").setAttribute("aria-pressed", String(!engine));
  $("view-engine").setAttribute("aria-pressed", String(engine));
}
$("view-page").addEventListener("click", () => showView("page"));
$("view-engine").addEventListener("click", () => showView("engine"));

// Buttons on the trace box: pause, clear, copy the last call as curl.
$("trace-pause").addEventListener("click", () => {
  tracePaused = !tracePaused;
  $("trace-pause").textContent = tracePaused ? "Resume" : "Pause";
  $("trace-pause").setAttribute("aria-pressed", String(tracePaused));
});
$("trace-clear").addEventListener("click", () => { $("trace").innerHTML = ""; $("engine-log").innerHTML = ""; });
$("trace-copy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(lastCurl); $("trace-copy").textContent = "Copied"; }
  catch (e) { $("trace-copy").textContent = "Select the line and copy"; }
  setTimeout(() => { $("trace-copy").textContent = "Copy last as curl"; }, 1500);
});

// Light / dark, remembered in this browser only.
function setTheme(dark) {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  $("theme").textContent = dark ? "Light mode" : "Dark mode"; $("theme").setAttribute("aria-pressed", String(dark));
  try { localStorage.setItem("cte-theme", dark ? "dark" : "light"); } catch (e) {}
  if (chart) { chart.destroy(); chart = null; refresh(); }
}
$("theme").addEventListener("click", () => setTheme(document.documentElement.getAttribute("data-theme") !== "dark"));

// Which engine to talk to. Normally the same address as this page. On the
// website you can point it at the engine on your own laptop with
//   https://ansh-bhargav.web.app/centralized-trading-engine/?api=http://localhost:8000
const wanted = new URLSearchParams(location.search).get("api");
if (wanted && /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(wanted)) API = wanted;

$("connect").addEventListener("click", () => {
  location.search = "?api=http://localhost:8000";   // reload, talking to the engine on this laptop
});

// Start: is the API here? If not, fall back to snapshot.json (static website mode).
(async function start() {
  let dark = false; try { dark = localStorage.getItem("cte-theme") === "dark"; } catch (e) {}
  setTheme(dark);
  traceLine("meta", "Call trace: every request this page sends to the API, as a curl command.");
  try { const r = await fetch(API + "/health"); if (!r.ok) throw 0; await r.json(); }
  catch (e) {
    try { SNAPSHOT = await (await fetch("snapshot.json")).json(); } catch (e2) { SNAPSHOT = null; }
    if (SNAPSHOT) {
      $("docs-link").href = "api.html"; $("docs-link").textContent = "static copy of the API menu";
      traceLine("meta", "SNAPSHOT mode: no engine here, so answers come from snapshot.json. Run the engine on a laptop to see live calls.");
      traceLine("meta", "SNAPSHOT mode: the engine log needs a running engine. Start it (python run.py), then press 'Use my laptop engine'.", "engine-log");
      $("connect").hidden = false;
    }
  }
  refresh();
  if (!SNAPSHOT) { setInterval(refresh, 3000); setInterval(pollEngineLog, 2000); pollEngineLog(); }
  if (API) traceLine("meta", "Talking to the engine at " + API);
})();

// Code map: click the mode badge to see what each file does, with links to GitHub.
$("badge").addEventListener("click", () => $("codemap").showModal());
$("cm-close").addEventListener("click", () => $("codemap").close());
