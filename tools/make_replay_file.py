"""Make the MOCK replay file used for demos and tests.

In plain words:
    We cannot ship a real recording of Binance inside the repository forever,
    and tests must never need the internet. So this script writes a pretend
    recording: about 90 minutes of BTCUSDT deals that wander up and down, in
    exactly Binance's message format. Every price in it is MOCK (made up).

    It also slips in a few bad messages on purpose (a missing price, a
    repeated trade, a ticker) so you can watch Clean throw them in the bin.

Run:  python tools/make_replay_file.py
"""
import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "replay" / "btcusdt_mock.jsonl"


def main():
    rng = random.Random(26)              # fixed seed: same file every time
    t = 1795300000000                    # a fixed start time (ms since 1970, UTC)
    trade_id, price, lines = 4100000, 67000.0, []
    for i in range(2400):                # about one deal every 2.25 s -> ~90 minutes
        t += rng.randint(1200, 3300)
        trade_id += 1
        drift = 7.0 * math.sin(i / 120.0)   # slow waves so the averages cross a few times
        price = max(1000.0, price + drift + rng.gauss(0, 6))
        msg = {"e": "trade", "E": t + 3, "s": "BTCUSDT", "t": trade_id,
               "p": f"{price:.2f}", "q": f"{rng.choice([0.0005, 0.001, 0.0031, 0.002, 0.01]):.4f}",
               "T": t, "m": rng.random() < 0.5, "M": True}
        lines.append({"stream": "btcusdt@trade", "data": msg})
        if i % 40 == 0:                  # a ticker roughly every 90 s
            lines.append({"stream": "btcusdt@ticker", "data": {"e": "24hrTicker", "E": t + 5, "s": "BTCUSDT", "c": f"{price:.2f}", "v": "1234.5"}})
        if i in (300, 1300):             # a broken message: price missing
            bad = dict(msg); bad.pop("p"); lines.append({"stream": "btcusdt@trade", "data": bad})
        if i in (700, 1900):             # the same deal sent twice
            lines.append({"stream": "btcusdt@trade", "data": msg})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    print("wrote", OUT, len(lines), "messages (MOCK data)")


if __name__ == "__main__":
    main()
