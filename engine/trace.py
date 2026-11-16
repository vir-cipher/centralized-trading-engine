"""The engine's own call log (the "black screen").

In plain words:
    Every request that reaches our API, and every call our engine makes to
    Binance, is written down here as one short line, like a terminal would:

        14:32:05  GET  /prices/BTCUSDT                -> 200   3 ms
        14:32:09  POST /orders  key=****              -> 201  41 ms
        14:32:09    -> Binance POST /v3/order  symbol=BTCUSDT side=BUY ...  signature=1f9c...e2 (64 hex)

    The same line is printed in the window where the engine runs, and kept in
    memory (newest 300 lines) so the dashboard can show it through GET /trace.

    Secrets never get written: the API key is shown as **** and the HMAC
    signature is cut to its first and last characters.
"""

import itertools
import time
from collections import deque

_lines = deque(maxlen=300)          # newest 300 lines only
_ids = itertools.count(1)           # every line gets a number, so the page asks "what is new since 41?"


def log(kind, text):
    """Add one line. kind is "in" (request to us), "out" (our call to Binance) or "note"."""
    item = {"id": next(_ids), "t": time.strftime("%H:%M:%S"), "kind": kind, "text": text}
    _lines.append(item)
    print(f"{item['t']}  {text}", flush=True)   # the same line in the engine's own window
    return item


def since(after_id=0):
    """All lines newer than after_id, oldest first."""
    return [x for x in _lines if x["id"] > after_id]


def short_signature(sig):
    """1f9c4b...0be2 style: enough to see it is there, not enough to reuse."""
    return sig[:4] + "..." + sig[-4:] + f" ({len(sig)} hex)" if sig else "-"
