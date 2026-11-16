"""Centralized Trading Engine: listen, clean, store, advise, forward signed orders.

Read the files in this order (each one is one step of the pipe):
    sources.py   -> where messages come from (LIVE Binance Testnet or REPLAY file)
    clean.py     -> turn each message into one tidy row
    store.py     -> keep rows in SQLite
    pipeline.py  -> the loop that ties the three together
    signals.py   -> BUY / SELL / HOLD advice from two averages
    exchange.py  -> signed orders (or a pretend exchange)
    api.py       -> the web API and its /docs menu
"""
