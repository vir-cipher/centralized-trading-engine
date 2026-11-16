"""Orders: talk to Binance Testnet with a signed request, or to a pretend exchange.

In plain words:
    Reading prices is public, like reading a notice board. Placing an order is
    private, like writing a cheque. Binance needs proof that the order really
    comes from us and was not changed on the way. That proof is a SEAL
    (signature) made with our secret key.

    The secret key never leaves the laptop. We send:
        the order text  +  the seal  +  our API key (in the X-MBX-APIKEY header)
    Binance keeps its own copy of the secret, seals the same text again and
    compares. Same seal -> accepted. Different seal -> rejected.

    Binance also checks the time stamp. If the laptop clock is more than
    `recvWindow` milliseconds off, a perfect seal still fails (error -1021).

Two exchanges live in this file:
    TestnetExchange  the real practice market (needs keys and internet)
    FakeExchange     a pretend one for tests and REPLAY mode (no internet, no keys)
Both have the same three methods, so the rest of the code does not care which
one it is talking to.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode


def sign(query_string, secret):
    """Make the HMAC-SHA256 seal for one request.

    Args:
        query_string: the order text, e.g. "symbol=BTCUSDT&side=BUY&...&timestamp=..."
        secret: the secret key (text)

    Returns:
        64 hexadecimal characters. Binance's own documentation gives a worked
        example; tests/test_exchange.py checks we get exactly the same seal.
    """
    return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()


def signed_query(params, secret, recv_window=5000, now_ms=None):
    """Add the time stamp and window, then append the seal. Returns the full query text.

    The order matters: the seal must be made over exactly the text we send,
    so we build the text first, seal it, then add &signature=... at the end.
    """
    params = dict(params)
    params["recvWindow"] = recv_window
    params["timestamp"] = now_ms if now_ms is not None else int(time.time() * 1000)
    text = urlencode(params)
    return text + "&signature=" + sign(text, secret)


class ExchangeError(Exception):
    """Binance said no. `code` is Binance's error number, e.g. -2010 (rejected, often balance)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class TestnetExchange:
    """The real Binance Spot Testnet, over HTTPS with the `httpx` library."""

    def __init__(self, rest_url, api_key, api_secret, recv_window=5000):
        import httpx  # imported here so tests without httpx still load this file

        if not api_key or not api_secret:
            raise ValueError("Testnet keys missing: put them in .env (see .env.example)")
        self.http = httpx.Client(base_url=rest_url, timeout=10, headers={"X-MBX-APIKEY": api_key})
        self.secret = api_secret
        self.recv_window = recv_window

    def _signed(self, method, path, params):
        query = signed_query(params, self.secret, self.recv_window)
        resp = self.http.request(method, path + "?" + query)
        data = resp.json()
        if resp.status_code != 200:
            raise ExchangeError(data.get("code", resp.status_code), data.get("msg", "Binance error"))
        return data

    def place_order(self, client_id, symbol, side, type_, qty, price=None):
        params = {"symbol": symbol, "side": side, "type": type_, "quantity": qty, "newClientOrderId": client_id}
        if type_ == "LIMIT":
            params.update({"price": price, "timeInForce": "GTC"})  # GTC = stays open until filled or cancelled
        data = self._signed("POST", "/v3/order", params)
        fills = data.get("fills") or []
        filled_price = (sum(float(f["price"]) * float(f["qty"]) for f in fills) / sum(float(f["qty"]) for f in fills)) if fills else None
        return {"status": data.get("status", "NEW"), "exchange_id": str(data.get("orderId")), "filled_price": filled_price}

    def cancel_order(self, client_id, symbol):
        data = self._signed("DELETE", "/v3/order", {"symbol": symbol, "origClientOrderId": client_id})
        return {"status": data.get("status", "CANCELED")}

    def balances(self):
        data = self._signed("GET", "/v3/account", {})
        return [{"asset": b["asset"], "free": float(b["free"]), "locked": float(b["locked"])}
                for b in data.get("balances", []) if float(b["free"]) or float(b["locked"])]


class FakeExchange:
    """A pretend exchange: same methods, no internet, made-up balances.

    Every order it handles is marked "SIMULATED", so nobody mistakes it for a Testnet order.

    In plain words:
        Used in tests and in REPLAY mode so the whole app works with Wi-Fi off.
        A MARKET order fills at once at the last known price. A LIMIT order
        waits (status NEW) until someone cancels it. Balances are toy money.
    """

    def __init__(self, last_price_of):
        self.last_price_of = last_price_of     # a function: symbol -> last price or None
        self.balance = {"USDT": 10000.0, "BTC": 1.0}
        self.next_id = 1

    def place_order(self, client_id, symbol, side, type_, qty, price=None):
        oid = str(self.next_id)
        self.next_id += 1
        if type_ == "LIMIT":
            return {"status": "NEW", "exchange_id": oid, "filled_price": None, "note": "SIMULATED"}
        last = self.last_price_of(symbol)
        if last is None:
            raise ExchangeError(-1013, "no price yet for " + symbol)
        cost = last * qty
        if side == "BUY" and cost > self.balance["USDT"]:
            raise ExchangeError(-2010, "Account has insufficient balance for requested action.")
        if side == "SELL" and qty > self.balance["BTC"]:
            raise ExchangeError(-2010, "Account has insufficient balance for requested action.")
        sign_ = 1 if side == "BUY" else -1
        self.balance["USDT"] -= sign_ * cost
        self.balance["BTC"] += sign_ * qty
        return {"status": "FILLED", "exchange_id": oid, "filled_price": last, "note": "SIMULATED"}

    def cancel_order(self, client_id, symbol):
        return {"status": "CANCELED"}

    def balances(self):
        return [{"asset": a, "free": round(v, 8), "locked": 0.0} for a, v in self.balance.items()]
