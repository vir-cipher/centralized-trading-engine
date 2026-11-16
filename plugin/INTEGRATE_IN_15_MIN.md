# Integrate with the Centralized Trading Engine in 15 minutes

For the team building a plugin on top of our engine. You do not need Binance keys, and you do not need our live engine to start: run it in REPLAY mode on your own laptop.

## 1. Run the engine (3 minutes)
```bash
git clone <this repository>
cd centralized-trading-engine
pip install -r requirements.txt
python run.py            # REPLAY mode: recorded MOCK data, no internet needed
```
Open http://localhost:8000/docs. That page is the full menu, with a "Try it out" button on every route.

REPLAY is our mock server: the same routes and the same answers as LIVE, just with recorded MOCK data.

## 2. Read data (2 minutes)
Reading needs no key.

| You want | Call | You get (example) |
|---|---|---|
| Latest price | `GET /prices/BTCUSDT` | `{"symbol":"BTCUSDT","price":67012.5,"ts":1795301234567,"source":"REPLAY"}` |
| Advice | `GET /signals/BTCUSDT` | `{"advice":"HOLD","reason":"no fresh crossing this minute","advisory_only":true,...}` |
| One-minute candles | `GET /candles?symbol=BTCUSDT&limit=60` | `[{"minute_start_ms":...,"open":...,"high":...,"low":...,"close":...,"volume":...}]` |
| Recent deals | `GET /trades?symbol=BTCUSDT&limit=20` | `[{"trade_id":4119203,"price":67012.5,"qty":0.0031,...}]` |
| Engine status | `GET /health` | `{"ok":true,"mode":"REPLAY",...}` |

`source` tells you whether a price is LIVE (Binance Testnet) or REPLAY (recorded). Always show it to your users.

## 3. Place and cancel orders (5 minutes)
Writing needs a key in the header: `X-API-Key: demo-plugin-key`. Ask us for your own key before demo day.

```bash
curl -X POST localhost:8000/orders -H "X-API-Key: demo-plugin-key" -H "Content-Type: application/json" \
     -d '{"symbol":"BTCUSDT","side":"BUY","type":"MARKET","qty":0.001}'
curl -X DELETE localhost:8000/orders/2 -H "X-API-Key: demo-plugin-key"
```
- `MARKET` fills at once (status `FILLED`).
- `LIMIT` needs `price` and waits (status `NEW`) until it fills or you cancel it.
- Cancel works only on open orders. A fill cannot be undone.

## 4. Handle errors (2 minutes)
Every error has the same shape:
```json
{"error": {"code": "BAD_API_KEY", "message": "send a valid X-API-Key header to place or cancel orders"}}
```

| HTTP | code | Meaning | What to do |
|---|---|---|---|
| 400 | `PRICE_REQUIRED` | LIMIT order without a price | Send `price` |
| 400 | `NOT_OPEN` | Cancelling a filled or cancelled order | Nothing to cancel |
| 401 | `BAD_API_KEY` | Missing or wrong `X-API-Key` | Check the key |
| 404 | `NOT_FOUND` | No data yet for that symbol, or no such order | Check the symbol or id |
| 422 | (FastAPI) | Body has the wrong shape | Compare with `/docs` |
| 502 | `EXCHANGE_-2010` | Binance rejected the order, often for balance | Smaller quantity |
| 502 | `EXCHANGE_-1021` | Laptop clock out of step with Binance | Sync the clock |

## 5. Copy a working client (3 minutes)
- Python: `plugin/examples/client.py` (10 lines, uses `httpx`)
- Browser: `plugin/examples/client.html` (calls the API with `fetch`; CORS is open by default)

## Contract and versions
- `plugin/openapi.json` is the machine-readable contract. Generate your client from it, or import it into Postman or Bruno.
- `plugin/CHANGELOG.md` lists every change. We never rename a field within the same MAJOR version.
- Questions or a broken route: open an issue in this repository.
