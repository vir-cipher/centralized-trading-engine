"""Clean: turn every messy Binance message into one tidy row (the T in ETL).

In plain words:
    Binance shouts each deal at us as a little JSON note, with short cryptic
    names ("p" for price, "q" for quantity) and numbers written as text
    ("67012.50" in quotes). The clerk in this file rewrites each note into the
    same neat row, every time, and throws away notes that are broken or
    already written down.

The clean row (our data contract; every other file relies on these names):

    field      type    example            meaning
    event      str     "TRADE"            what kind of message it was
    symbol     str     "BTCUSDT"          coin pair
    price      float   67012.5            price of this one deal
    qty        float   0.0031             how much changed hands
    ts         int     1795301234567      deal time, milliseconds since 1970 (UTC)
    trade_id   int     4119203            Binance's number for this deal
    source     str     "LIVE" / "REPLAY"  where the row came from

Binance trade message (one deal), as documented by Binance:
    {"e": "trade", "E": event time, "s": symbol, "t": trade id,
     "p": "price as text", "q": "quantity as text", "T": trade time, "m": ..., "M": ...}
"""

# Fields we need from a trade message, and what each becomes.
# In plain words: "take note field p and call it price", and so on.
TRADE_FIELDS = {"s": "symbol", "p": "price", "q": "qty", "T": "ts", "t": "trade_id"}


def unwrap(message):
    """Return the inner message if Binance wrapped it.

    In plain words:
        When we listen to several streams on one line, Binance puts each note
        inside an envelope: {"stream": "btcusdt@trade", "data": {...note...}}.
        This opens the envelope. A note without an envelope is returned as is.
    """
    if isinstance(message, dict) and "data" in message and "stream" in message:
        return message["data"]
    return message


class Cleaner:
    """The clerk. Remembers which trades it has already written down.

    In plain words:
        A function alone cannot remember anything between calls. We need the
        clerk to remember trade numbers it has seen, so that a repeated note is
        not written twice. That memory is `self.seen`.
    """

    def __init__(self, source="LIVE"):
        self.source = source      # "LIVE" or "REPLAY", stamped on every row
        self.seen = set()         # trade numbers already written down
        self.rejected = {}        # reason -> how many notes were thrown away for it

    def _reject(self, reason):
        """Count one thrown-away note under its reason, then return None."""
        self.rejected[reason] = self.rejected.get(reason, 0) + 1
        return None

    def clean(self, message):
        """Turn one raw trade message into one clean row, or None if it is bad.

        Steps, in order:
            1. open the envelope (if any)
            2. keep only trade messages (a ticker is a different kind of note)
            3. check all five fields are present
            4. turn text into numbers
            5. refuse zero/negative price or quantity
            6. refuse a trade number we have already stored

        Returns:
            dict with the fields listed at the top of this file, or None.

        Example:
            >>> Cleaner(source="REPLAY").clean({"e": "trade", "s": "BTCUSDT", "p": "67012.50",
            ...     "q": "0.0031", "T": 1795301234567, "t": 4119203})["price"]
            67012.5
        """
        msg = unwrap(message)
        if not isinstance(msg, dict):
            return self._reject("not a JSON object")

        # Step 2. Why check the type? A ticker message also has a quantity
        # ("v"), but it is a whole day's total, not one deal. Mixing them would
        # make the numbers lie.
        if msg.get("e") != "trade":
            return self._reject("not a trade message")

        # Step 3. Every field must be there.
        for short_name in TRADE_FIELDS:
            if short_name not in msg or msg[short_name] in (None, ""):
                return self._reject("missing " + TRADE_FIELDS[short_name])

        # Step 4. Text -> numbers. float("abc") raises ValueError; we catch it.
        try:
            price = float(msg["p"])
            qty = float(msg["q"])
            ts = int(msg["T"])
            trade_id = int(msg["t"])
        except (TypeError, ValueError):
            return self._reject("not a number")

        # Step 5. A price or amount of zero or less cannot be a real deal.
        if price <= 0 or qty <= 0:
            return self._reject("zero or negative")

        # Step 6. Same trade number again? Binance can resend after a reconnect.
        key = (str(msg["s"]).upper(), trade_id)
        if key in self.seen:
            return self._reject("duplicate")
        self.seen.add(key)

        return {
            "event": "TRADE",
            "symbol": str(msg["s"]).upper(),
            "price": price,
            "qty": qty,
            "ts": ts,
            "trade_id": trade_id,
            "source": self.source,
        }


def ticker_price(message):
    """Read the last price from a 24-hour ticker message, or None.

    In plain words:
        The ticker is Binance's scoreboard, sent about once a second. We use
        it only to know the latest price; we never store it as a trade.
        Field "c" is the last price, written as text.
    """
    msg = unwrap(message)
    if isinstance(msg, dict) and msg.get("e") == "24hrTicker":
        try:
            return str(msg["s"]).upper(), float(msg["c"])
        except (KeyError, TypeError, ValueError):
            return None
    return None
