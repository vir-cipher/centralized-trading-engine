"""Signing must match Binance's own documented example exactly; the pretend exchange must behave."""
import pytest

from engine.exchange import ExchangeError, FakeExchange, sign, signed_query

# Worked example from the Binance Spot API documentation ("SIGNED endpoint examples for POST /api/v3/order").
DOC_SECRET = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
DOC_QUERY = "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1&recvWindow=5000&timestamp=1499827319559"
DOC_SIGNATURE = "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"


def test_seal_matches_binance_documentation():
    assert sign(DOC_QUERY, DOC_SECRET) == DOC_SIGNATURE


def test_signed_query_ends_with_the_seal_of_everything_before_it():
    q = signed_query({"symbol": "BTCUSDT"}, "s3cret", recv_window=5000, now_ms=1)
    body, seal = q.rsplit("&signature=", 1)
    assert body == "symbol=BTCUSDT&recvWindow=5000&timestamp=1"
    assert seal == sign(body, "s3cret")


def test_secret_never_appears_in_what_we_send():
    assert "s3cret" not in signed_query({"symbol": "BTCUSDT"}, "s3cret", now_ms=1)


def test_fake_market_order_fills_at_last_price():
    ex = FakeExchange(lambda s: 67000.0)
    assert ex.place_order("c1", "BTCUSDT", "BUY", "MARKET", 0.01) == {"status": "FILLED", "exchange_id": "1", "filled_price": 67000.0, "note": "SIMULATED"}


def test_fake_limit_order_waits():
    assert FakeExchange(lambda s: 1.0).place_order("c1", "BTCUSDT", "BUY", "LIMIT", 1, 0.5)["status"] == "NEW"


def test_fake_insufficient_balance_is_minus_2010():
    with pytest.raises(ExchangeError) as e:
        FakeExchange(lambda s: 67000.0).place_order("c1", "BTCUSDT", "BUY", "MARKET", 100)
    assert e.value.code == -2010
