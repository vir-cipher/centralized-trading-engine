"""The whole engine through its web API, in REPLAY mode, with no internet.

We feed the MOCK replay file straight into the pipeline (fast), then call the
routes exactly as the dashboard or another team's plugin would.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app

REPLAY = Path(__file__).resolve().parent.parent / "data" / "replay" / "btcusdt_mock.jsonl"
KEY = {"X-API-Key": "demo-plugin-key"}


@pytest.fixture()
def loaded(tmp_path):
    app = create_app(mode="replay", db_path=tmp_path / "t.sqlite3", start_background=False)
    with TestClient(app) as c:
        pipe = c.app.state.pipe
        for line in REPLAY.read_text(encoding="utf-8").splitlines():
            pipe.handle(json.loads(line), "REPLAY")
        yield c


def test_health_counts_trades_and_rejects(loaded):
    h = loaded.get("/health").json()
    assert h["ok"] and h["mode"] == "REPLAY" and h["trades_stored"] == 2400
    assert h["rejected"]["REPLAY"]["missing price"] == 2
    assert h["rejected"]["REPLAY"]["duplicate"] == 2


def test_price_and_unknown_symbol(loaded):
    p = loaded.get("/prices/btcusdt").json()
    assert p["symbol"] == "BTCUSDT" and p["price"] > 0 and p["source"] == "REPLAY"
    e = loaded.get("/prices/ETHUSDT")
    assert e.status_code == 404 and e.json()["error"]["code"] == "NOT_FOUND"


def test_candles_and_trades(loaded):
    c = loaded.get("/candles", params={"symbol": "BTCUSDT", "limit": 10}).json()
    assert len(c) == 10 and c[0]["minute_start_ms"] < c[-1]["minute_start_ms"]
    assert all(x["low"] <= x["close"] <= x["high"] for x in c)
    assert len(loaded.get("/trades", params={"limit": 5}).json()) == 5


def test_signal_is_advice_only(loaded):
    s = loaded.get("/signals/BTCUSDT").json()
    assert s["advice"] in ("BUY", "SELL", "HOLD") and s["advisory_only"] is True
    assert s["honest_test"]["scored_minutes"] > 0


def test_order_needs_key(loaded):
    r = loaded.post("/orders", json={"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "qty": 0.001})
    assert r.status_code == 401 and r.json()["error"]["code"] == "BAD_API_KEY"


def test_market_order_fills_and_limit_can_be_cancelled(loaded):
    m = loaded.post("/orders", headers=KEY, json={"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "qty": 0.001}).json()
    assert m["status"] == "FILLED" and m["filled_price"] > 0
    lim = loaded.post("/orders", headers=KEY, json={"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "qty": 0.001, "price": 1000}).json()
    assert lim["status"] == "NEW"
    cancelled = loaded.delete(f"/orders/{lim['id']}", headers=KEY).json()
    assert cancelled["status"] == "CANCELED"
    again = loaded.delete(f"/orders/{m['id']}", headers=KEY)          # a fill cannot be undone
    assert again.status_code == 400 and again.json()["error"]["code"] == "NOT_OPEN"
    assert len(loaded.get("/orders").json()) == 2


def test_limit_without_price_is_400(loaded):
    r = loaded.post("/orders", headers=KEY, json={"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "qty": 0.001})
    assert r.json()["error"]["code"] == "PRICE_REQUIRED"


def test_balance_is_toy_money(loaded):
    assets = {b["asset"] for b in loaded.get("/account/balance").json()}
    assert {"USDT", "BTC"} <= assets
