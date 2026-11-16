# API changelog

The API follows semantic versioning: MAJOR.MINOR.PATCH.
- MAJOR changes can break your plugin (a field renamed or removed). We announce them first.
- MINOR adds something new; your plugin keeps working.
- PATCH fixes a bug; nothing changes for you.

## 1.0.0 — 16 Nov 2026
- First public version.
- Routes: `GET /health`, `GET /prices/{symbol}`, `GET /trades`, `GET /candles`, `GET /signals/{symbol}`, `GET /account/balance`, `GET /orders`, `POST /orders`, `DELETE /orders/{id}`.
- Writing routes need `X-API-Key`.
- One error shape for every error: `{"error": {"code", "message"}}`.
