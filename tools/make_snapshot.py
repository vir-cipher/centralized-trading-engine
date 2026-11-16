"""Freeze the dashboard's data into dashboard/snapshot.json, for a static website.

In plain words:
    A static website (Firebase Hosting, GitHub Pages) can show files but cannot
    run Python. So we run the engine once here, on the MOCK replay file, ask it
    every question the dashboard asks, and save the answers in one file. The
    dashboard reads that file when it cannot reach a live API, and shows a
    SNAPSHOT badge so nobody mistakes it for live data.

Run:  python tools/make_snapshot.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from engine.api import create_app  # noqa: E402

PATHS = ["/candles?symbol=BTCUSDT&limit=120", "/prices/BTCUSDT", "/signals/BTCUSDT",
         "/trades?symbol=BTCUSDT&limit=12", "/orders", "/health"]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(mode="replay", db_path=Path(tmp) / "snap.sqlite3", start_background=False)
        with TestClient(app) as c:
            for line in (ROOT / "data" / "replay" / "btcusdt_mock.jsonl").read_text(encoding="utf-8").splitlines():
                c.app.state.pipe.handle(json.loads(line), "REPLAY")
            snap = {p: c.get(p).json() for p in PATHS}
    out = ROOT / "dashboard" / "snapshot.json"
    out.write_text(json.dumps(snap, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
