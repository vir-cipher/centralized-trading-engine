"""The clerk at the end of the belt: take a message, clean it, store it.

In plain words:
    This loop runs forever in the background. It waits for the next message
    on the belt, asks the Cleaner to turn it into a tidy row, writes the row
    into SQLite, and remembers the latest price in memory so the API can
    answer "what is BTC now?" instantly without opening the database.
"""

import asyncio

from . import store
from .clean import Cleaner, ticker_price


class Pipeline:
    """Holds everything the running engine shares: the belt, the clerk, the latest prices."""

    def __init__(self, db):
        self.db = db
        self.queue = asyncio.Queue(maxsize=10000)   # the conveyor belt
        self.cleaners = {"LIVE": Cleaner("LIVE"), "REPLAY": Cleaner("REPLAY")}
        self.latest = {}       # symbol -> {"price": ..., "ts": ..., "source": ...}
        self.mode = "REPLAY"   # shown on the dashboard badge
        self.stored = 0

    def last_price(self, symbol):
        """Latest price for a symbol, from memory first, then from the database."""
        if symbol in self.latest:
            return self.latest[symbol]["price"]
        row = store.last_trade(self.db, symbol)
        return row["price"] if row else None

    def handle(self, message, source):
        """Process one message. Kept separate from the loop so tests can call it directly."""
        tick = ticker_price(message)
        if tick:
            symbol, price = tick
            self.latest[symbol] = {"price": price, "ts": None, "source": source}
            return None
        row = self.cleaners[source].clean(message)
        if row is None:
            return None
        if store.save_trade(self.db, row):
            self.stored += 1
        self.latest[row["symbol"]] = {"price": row["price"], "ts": row["ts"], "source": source}
        self.mode = source
        return row

    async def run(self, stop):
        """Forever: wait for a message on the belt, then handle it."""
        while not stop.is_set():
            try:
                message, source = await asyncio.wait_for(self.queue.get(), timeout=1)
            except asyncio.TimeoutError:
                continue
            self.handle(message, source)

    def rejected(self):
        """How many messages each clerk threw away, by reason."""
        return {src: dict(c.rejected) for src, c in self.cleaners.items()}
