# Start here: the whole engine in everyday words

## The picture
Think of a **bazaar** where traders shout prices all day.

| In the bazaar | In our code | File |
|---|---|---|
| Someone hears every shout and never misses one | **Listener**: one WebSocket line kept open to Binance | `engine/sources.py` |
| A conveyor belt between the listener and the clerk | **Queue**: `asyncio.Queue` | `engine/pipeline.py` |
| A clerk rewrites each shout neatly in a ledger, and bins the garbled ones | **Clean**: one tidy row per deal; broken or repeated messages go to the bin | `engine/clean.py` |
| The ledger | **SQLite**: one database file on the laptop | `engine/store.py` |
| An uncle who compares today's mood with this week's and says buy or sell, but only advises | **Signal**: 5-minute vs 15-minute moving average | `engine/signals.py` |
| A counter window that takes your order, seals it so nobody can forge it, and hands it over | **Orders**: HMAC-SHA256 signature, then Binance REST | `engine/exchange.py` |
| A menu on the door so other shops can trade through us | **API**: FastAPI, menu at `/docs` | `engine/api.py` |
| A notice board everyone can read | **Dashboard** | `dashboard/` |
| All with toy money, in a practice bazaar with its own prices | **Binance Spot Testnet** | — |

## What our engine is NOT
- **Not an exchange.** Binance matches buyers and sellers; we only pass orders on.
- **Not a bot.** The advice never places an order. A human clicks.

## Words you will hear
| Word | Plain meaning |
|---|---|
| BTCUSDT | Bitcoin priced in USDT, a dollar-like coin |
| Trade | One deal: a price, an amount and a time |
| Ticker | Binance's scoreboard, sent every second; it is not a deal |
| WebSocket | A phone line that stays open, so Binance can talk to us any time |
| REST API | Ask a question, get one answer, hang up |
| Moving average | The average of the last few prices; it smooths out the jumps |
| HMAC-SHA256 | A seal made from the message and a secret key; it proves who sent it |
| REPLAY | Playing a recording through the same pipes when the live market is unavailable |
