"""Store: keep every clean row and every order in one SQLite file (the L in ETL).

In plain words:
    SQLite is a whole database inside one ordinary file on the laptop. No
    server to install. We write clean trades and our orders into it, and read
    them back for the chart, the candles and the signal.

Tables:
    trades  one row per clean deal (see clean.py for the fields)
    orders  one row per order a user placed through our API
"""

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    symbol    TEXT    NOT NULL,
    trade_id  INTEGER NOT NULL,
    price     REAL    NOT NULL,
    qty       REAL    NOT NULL,
    ts        INTEGER NOT NULL,          -- milliseconds since 1970, UTC
    source    TEXT    NOT NULL,          -- LIVE or REPLAY
    PRIMARY KEY (symbol, trade_id)       -- the same deal can never be stored twice
);
CREATE INDEX IF NOT EXISTS trades_by_time ON trades (symbol, ts);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     TEXT    NOT NULL UNIQUE,  -- our name for the order, also sent to Binance
    symbol        TEXT    NOT NULL,
    side          TEXT    NOT NULL,         -- BUY or SELL
    type          TEXT    NOT NULL,         -- MARKET or LIMIT
    qty           REAL    NOT NULL,
    price         REAL,                     -- only for LIMIT orders
    status        TEXT    NOT NULL,         -- NEW, FILLED, CANCELED, REJECTED ...
    exchange_id   TEXT,                     -- Binance's own order number
    filled_price  REAL,
    created_ms    INTEGER NOT NULL,
    note          TEXT
);
"""


def connect(path):
    """Open (or create) the database file and make sure the tables exist.

    In plain words:
        If the file is not there yet, SQLite creates it. `row_factory` makes
        each row behave like a dictionary, so we can write row["price"]
        instead of row[2].
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def save_trade(db, row):
    """Write one clean row. Returns True if new, False if it was already there.

    `INSERT OR IGNORE` + the primary key means a repeated deal is skipped
    quietly instead of crashing the program.
    """
    cur = db.execute(
        "INSERT OR IGNORE INTO trades (symbol, trade_id, price, qty, ts, source) VALUES (?, ?, ?, ?, ?, ?)",
        (row["symbol"], row["trade_id"], row["price"], row["qty"], row["ts"], row["source"]),
    )
    db.commit()
    return cur.rowcount == 1


def recent_trades(db, symbol, limit=20):
    """The newest deals first, as plain dictionaries."""
    rows = db.execute(
        "SELECT symbol, trade_id, price, qty, ts, source FROM trades WHERE symbol = ? ORDER BY ts DESC LIMIT ?",
        (symbol, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def last_trade(db, symbol):
    """The single newest deal for a symbol, or None if we have none yet."""
    rows = recent_trades(db, symbol, 1)
    return rows[0] if rows else None


def minute_candles(db, symbol, limit=60):
    """Group deals into one-minute candles: open, high, low, close, volume.

    In plain words:
        A candle summarises one minute: the first price (open), the highest,
        the lowest, the last price (close) and how much was traded. The
        signal uses the closes; the chart draws them.

    How it works:
        1. find the newest deal's minute, and go back `limit` minutes
        2. read those deals in time order
        3. walk through them, starting a new candle whenever the minute changes
        ts // 60000 turns milliseconds into a "minute number".
    """
    newest = db.execute("SELECT MAX(ts) FROM trades WHERE symbol = ?", (symbol,)).fetchone()[0]
    if newest is None:
        return []
    first_minute = newest // 60000 - (limit - 1)
    rows = db.execute(
        "SELECT price, qty, ts FROM trades WHERE symbol = ? AND ts >= ? ORDER BY ts, trade_id",
        (symbol, first_minute * 60000),
    ).fetchall()
    candles = []
    for price, qty, ts in rows:
        minute = ts // 60000
        if not candles or candles[-1]["minute"] != minute:
            candles.append({"minute": minute, "open": price, "high": price, "low": price, "close": price, "volume": 0.0})
        c = candles[-1]
        c["high"] = max(c["high"], price)
        c["low"] = min(c["low"], price)
        c["close"] = price          # the last deal of the minute so far
        c["volume"] += qty
    return [{"minute_start_ms": c["minute"] * 60000, "open": c["open"], "high": c["high"], "low": c["low"],
             "close": c["close"], "volume": round(c["volume"], 8)} for c in candles]


def save_order(db, order):
    """Insert a new order row and return its id number."""
    cur = db.execute(
        """INSERT INTO orders (client_id, symbol, side, type, qty, price, status, exchange_id, filled_price, created_ms, note)
           VALUES (:client_id, :symbol, :side, :type, :qty, :price, :status, :exchange_id, :filled_price, :created_ms, :note)""",
        {"exchange_id": None, "filled_price": None, "note": None, "created_ms": int(time.time() * 1000), **order},
    )
    db.commit()
    return cur.lastrowid


def update_order(db, order_id, **fields):
    """Change some columns of one order, e.g. status="CANCELED"."""
    if not fields:
        return
    names = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE orders SET {names} WHERE id = ?", (*fields.values(), order_id))
    db.commit()


def get_order(db, order_id):
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def list_orders(db, symbol=None, limit=50):
    if symbol:
        rows = db.execute("SELECT * FROM orders WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit)).fetchall()
    else:
        rows = db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
