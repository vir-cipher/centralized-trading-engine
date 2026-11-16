"""Smallest useful Python plugin: read the price and the advice, place one tiny order.

Run the engine first (python run.py), then:  python plugin/examples/client.py
Needs only the `httpx` library.
"""
import httpx

BASE = "http://localhost:8000"          # where the engine runs
KEY = {"X-API-Key": "demo-plugin-key"}  # ask the engine team for your own key

price = httpx.get(f"{BASE}/prices/BTCUSDT").json()
advice = httpx.get(f"{BASE}/signals/BTCUSDT").json()
print("BTCUSDT", price["price"], "from", price["source"], "| advice:", advice["advice"])

r = httpx.post(f"{BASE}/orders", headers=KEY, json={"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "qty": 0.001})
print("order:", r.json() if r.status_code == 200 else r.json()["error"])
