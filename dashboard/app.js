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

// Ask the API, or read the snapshot if we are on a static website.
async function get(path) {
  if (SNAPSHOT) return SNAPSHOT[path];
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
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
    $("reason").textContent = sig.reason + " (advice only)";
    const h = sig.honest_test;
    $("honest").textContent = h.rule_accuracy == null ? h.note
      : `Honest test on ${h.scored_minutes} later minutes: rule ${Math.round(h.rule_accuracy * 100)}% vs always-guess-the-commonest ${Math.round(h.baseline_accuracy * 100)}%`;
    $("trades").innerHTML = trades.map((t) => `<tr><td>${utc(t.ts)}</td><td>${fmt(t.price)}</td><td>${t.qty}</td></tr>`).join("");
    $("orders").innerHTML = orders.map((o) =>
      `<tr><td>${o.id}</td><td>${o.side === "BUY" ? "▲ BUY" : "▼ SELL"}</td><td>${o.type}</td><td>${o.qty}</td><td>${o.status}</td>` +
      `<td>${o.status === "NEW" && !SNAPSHOT ? `<button type="button" data-cancel="${o.id}">Cancel</button>` : ""}</td></tr>`).join("");
  } catch (e) {
    $("badge").textContent = "OFFLINE"; $("badge").className = "badge";
  }
}

// Place an order through our own API (needs the plugin key).
$("order").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (SNAPSHOT) { $("order-msg").textContent = "This is a static snapshot: orders work only when the engine runs on the laptop."; return; }
  const f = new FormData(ev.target), body = { symbol: SYMBOL, side: f.get("side"), type: f.get("type"), qty: Number(f.get("qty")) };
  if (body.type === "LIMIT") body.price = Number(f.get("price"));
  const r = await fetch(API + "/orders", { method: "POST", headers: { "Content-Type": "application/json", "X-API-Key": f.get("key") }, body: JSON.stringify(body) });
  const j = await r.json();
  $("order-msg").textContent = r.ok ? `Order ${j.id}: ${j.status}${j.filled_price ? " at " + fmt(j.filled_price) : ""}` : `Refused: ${j.error.code} (${j.error.message})`;
  refresh();
});

document.addEventListener("click", async (ev) => {
  const id = ev.target.getAttribute && ev.target.getAttribute("data-cancel");
  if (!id) return;
  const key = new FormData($("order")).get("key");
  const r = await fetch(API + "/orders/" + id, { method: "DELETE", headers: { "X-API-Key": key } });
  const j = await r.json();
  $("order-msg").textContent = r.ok ? `Order ${id}: ${j.status}` : `Refused: ${j.error.code}`;
  refresh();
});

// Light / dark, remembered in this browser only.
function setTheme(dark) {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  $("theme").textContent = dark ? "Light mode" : "Dark mode"; $("theme").setAttribute("aria-pressed", String(dark));
  try { localStorage.setItem("cte-theme", dark ? "dark" : "light"); } catch (e) {}
  if (chart) { chart.destroy(); chart = null; refresh(); }
}
$("theme").addEventListener("click", () => setTheme(document.documentElement.getAttribute("data-theme") !== "dark"));

// Start: is the API here? If not, fall back to snapshot.json (static website mode).
(async function start() {
  let dark = false; try { dark = localStorage.getItem("cte-theme") === "dark"; } catch (e) {}
  setTheme(dark);
  try { const r = await fetch("/health"); if (!r.ok) throw 0; await r.json(); }
  catch (e) {
    try { SNAPSHOT = await (await fetch("snapshot.json")).json(); } catch (e2) { SNAPSHOT = null; }
    if (SNAPSHOT) { $("docs-link").href = "api.html"; $("docs-link").textContent = "static copy of the API menu"; }
  }
  refresh();
  if (!SNAPSHOT) setInterval(refresh, 3000);
})();
