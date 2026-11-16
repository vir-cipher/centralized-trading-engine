# API changelog

The API follows semantic versioning: MAJOR.MINOR.PATCH.
- MAJOR changes can break your plugin (a field renamed or removed). We announce them first.
- MINOR adds something new; your plugin keeps working.
- PATCH fixes a bug; nothing changes for you.

## 1.1.0 — 16 Nov 2026
- New: `GET /trace?after=<id>` returns the engine's own call log: every API call it received and every signed call it sent to Binance (key shown as `****`, signature shortened).
- Responses now carry `Access-Control-Allow-Private-Network: true`, so the dashboard on the website can talk to an engine running on your own laptop.
- Nothing removed or renamed: plugins built on 1.0.0 keep working.

## 1.0.0 — 16 Nov 2026
- First public version.
- Routes: `GET /health`, `GET /prices/{symbol}`, `GET /trades`, `GET /candles`, `GET /signals/{symbol}`, `GET /account/balance`, `GET /orders`, `POST /orders`, `DELETE /orders/{id}`.
- Writing routes need `X-API-Key`.
- One error shape for every error: `{"error": {"code", "message"}}`.
