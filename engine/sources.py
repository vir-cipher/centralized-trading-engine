"""Listen: where the messages come from (the E in ETL).

In plain words:
    There are two ways messages can arrive, and both drop them onto the same
    conveyor belt (an asyncio.Queue):

    LIVE    one phone line kept open to Binance Testnet. Binance pushes every
            deal down it; we never ask. If the line drops, we redial.
    REPLAY  a recorded file of messages played back at speed. Used on demo
            night if Binance or the Wi-Fi is down, and in tests.

    After the belt, nothing can tell LIVE from REPLAY except the `source`
    label on each row. That is the whole trick of the demo-night plan.

Why a belt (queue) between listening and cleaning?
    The listener must answer the phone the moment it rings. If it also had
    to clean and save every message, a slow save could make it miss deals or
    miss Binance's ping. With a belt, the listener just drops each message
    and goes back to listening; the clerk picks them up at its own pace.

Binance facts the LIVE listener respects (Binance Spot Testnet docs):
    - combined stream URL: wss://stream.testnet.binance.vision/stream?streams=btcusdt@trade/btcusdt@ticker
    - a connection lives at most 24 hours, then Binance closes it -> we redial
    - Binance sends a ping every 20 seconds and expects a pong; the
      `websockets` library answers pings automatically for us
"""

import asyncio
import json
import logging

log = logging.getLogger("cte.sources")


def stream_url(base, symbols):
    """Build the combined-stream address for trades and tickers of every symbol.

    Example:
        >>> stream_url("wss://x/stream", ["BTCUSDT"])
        'wss://x/stream?streams=btcusdt@trade/btcusdt@ticker'
    """
    names = []
    for s in symbols:
        names += [s.lower() + "@trade", s.lower() + "@ticker"]
    return base + "?streams=" + "/".join(names)


async def listen_live(queue, base_url, symbols, stop):
    """Keep one WebSocket open to Binance and drop every message on the queue.

    Redials with a growing pause (1 s, 2 s, 4 s ... up to 30 s) whenever the
    line drops, until `stop` (an asyncio.Event) is set.
    """
    import websockets  # imported here so REPLAY mode works even without it

    url, pause = stream_url(base_url, symbols), 1
    while not stop.is_set():
        try:
            async with websockets.connect(url, ping_interval=None) as ws:
                # ping_interval=None: we do not send our own pings; Binance pings us
                # every 20 s and the library replies with a pong automatically.
                log.info("connected to %s", url)
                pause = 1
                async for text in ws:
                    await queue.put((json.loads(text), "LIVE"))
                    if stop.is_set():
                        break
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # network drop, 24-hour close, DNS failure ...
            log.warning("line dropped (%s); redialling in %s s", exc, pause)
            await asyncio.sleep(pause)
            pause = min(pause * 2, 30)


async def replay_file(queue, path, speed, stop, loop_forever=True, after_ts=None):
    """Play a recorded .jsonl file onto the queue, keeping the original gaps / speed.

    Each line of the file is one Binance message, exactly as it was received.
    With speed=20, a 20-second gap between two deals becomes 1 second.

    When the file ends we play it again, but shifted later in time and with
    new trade numbers, so the chart keeps moving instead of Clean throwing
    every repeated deal in the bin.

    after_ts: the time of the newest deal already in the ledger. After a restart
    we skip ahead to the first lap that starts later, so the old deals are not
    replayed as repeats (which would freeze the chart).
    """
    messages = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    times = [m.get("data", m).get("T") or m.get("data", m).get("E") for m in messages]
    ids = [m.get("data", m).get("t") for m in messages if m.get("data", m).get("t") is not None]
    span_ms = (max(times) - min(times)) + 60_000      # length of the recording plus one quiet minute
    id_step = (max(ids) - min(ids) + 1) if ids else 0
    lap = 0
    if after_ts is not None and after_ts >= min(times):
        lap = int((after_ts - min(times)) // span_ms) + 1
    while not stop.is_set():
        last_ts = None
        for msg in messages:
            if stop.is_set():
                return
            inner = dict(msg.get("data", msg))
            for key in ("T", "E"):                       # move the clock forward one lap
                if key in inner:
                    inner[key] += lap * span_ms
            if "t" in inner:                             # and give each deal a fresh number
                inner["t"] += lap * id_step
            ts = inner.get("T") or inner.get("E")
            if last_ts is not None and ts:
                await asyncio.sleep(max(0, (ts - last_ts) / 1000 / speed))
            last_ts = ts or last_ts
            await queue.put(({"stream": msg.get("stream", ""), "data": inner} if "data" in msg else inner, "REPLAY"))
        if not loop_forever:
            return
        lap += 1
