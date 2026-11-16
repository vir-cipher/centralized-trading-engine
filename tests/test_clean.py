"""Clean must turn good trade messages into rows and throw bad ones in the bin, with a reason."""
from engine.clean import Cleaner, ticker_price

GOOD = {"e": "trade", "E": 1795301234570, "s": "BTCUSDT", "t": 4119203,
        "p": "67012.50", "q": "0.0031", "T": 1795301234567, "m": True, "M": True}  # MOCK values


def test_good_message_becomes_clean_row():
    row = Cleaner("LIVE").clean(GOOD)
    assert row == {"event": "TRADE", "symbol": "BTCUSDT", "price": 67012.5, "qty": 0.0031,
                   "ts": 1795301234567, "trade_id": 4119203, "source": "LIVE"}


def test_text_becomes_number():
    row = Cleaner().clean(GOOD)
    assert isinstance(row["price"], float) and isinstance(row["trade_id"], int)


def test_envelope_from_combined_stream_is_opened():
    assert Cleaner().clean({"stream": "btcusdt@trade", "data": GOOD})["symbol"] == "BTCUSDT"


def test_missing_price_goes_in_bin():
    c = Cleaner()
    bad = dict(GOOD); bad.pop("p")
    assert c.clean(bad) is None
    assert c.rejected == {"missing price": 1}


def test_duplicate_trade_goes_in_bin():
    c = Cleaner()
    assert c.clean(GOOD) is not None
    assert c.clean(GOOD) is None
    assert c.rejected == {"duplicate": 1}


def test_negative_or_text_price_goes_in_bin():
    c = Cleaner()
    assert c.clean(dict(GOOD, p="-1")) is None
    assert c.clean(dict(GOOD, t=1, p="abc")) is None
    assert c.rejected == {"zero or negative": 1, "not a number": 1}


def test_ticker_is_not_a_trade_but_gives_a_price():
    tick = {"e": "24hrTicker", "s": "BTCUSDT", "c": "67000.10", "v": "1234.5"}
    assert Cleaner().clean(tick) is None          # never stored as a trade
    assert ticker_price(tick) == ("BTCUSDT", 67000.10)
