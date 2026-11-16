"""The replayer plays the file in order and, on the next lap, moves time and trade numbers forward."""
import asyncio
import json

from engine.sources import replay_file, stream_url


def test_stream_url_lists_trade_and_ticker():
    assert stream_url("wss://x/stream", ["BTCUSDT", "ETHUSDT"]) == \
        "wss://x/stream?streams=btcusdt@trade/btcusdt@ticker/ethusdt@trade/ethusdt@ticker"


def test_replay_second_lap_has_new_ids_and_later_times(tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text("\n".join(json.dumps({"stream": "btcusdt@trade", "data": {"e": "trade", "s": "BTCUSDT", "t": i, "p": "1", "q": "1", "T": 1000 * i}}) for i in (1, 2)) + "\n")

    async def go():
        q, stop = asyncio.Queue(), asyncio.Event()
        task = asyncio.create_task(replay_file(q, f, speed=1e9, stop=stop))
        got = [await q.get() for _ in range(4)]
        stop.set(); task.cancel()
        return got

    got = asyncio.run(go())
    ids = [m["data"]["t"] for m, _ in got]
    times = [m["data"]["T"] for m, _ in got]
    assert ids == [1, 2, 3, 4] and times[2] > times[1] and all(src == "REPLAY" for _, src in got)
