"""Start the whole engine with one command.

    python run.py            REPLAY mode: plays the recorded MOCK file (no internet, no keys)
    python run.py --live     LIVE mode: listens to Binance Spot Testnet (needs .env keys for orders)
    python run.py --auto     demo night: try LIVE, and switch to REPLAY by itself if nothing arrives in 15 s
    python run.py --openapi  writes plugin/openapi.json (the menu other teams build against) and stops

Then open in a browser:
    http://localhost:8000/        the dashboard
    http://localhost:8000/docs    the API menu (Swagger)

In plain words:
    uvicorn is the waiter that carries web requests to our FastAPI app.
    This file just picks the mode and asks uvicorn to start serving.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Centralized Trading Engine")
    ap.add_argument("--live", action="store_true", help="listen to Binance Spot Testnet instead of the replay file")
    ap.add_argument("--auto", action="store_true", help="try LIVE; fall back to REPLAY if Binance is unreachable")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--openapi", action="store_true", help="write plugin/openapi.json and exit")
    args = ap.parse_args()

    if args.live:
        os.environ["CTE_MODE"] = "live"
    elif args.auto:
        os.environ["CTE_MODE"] = "auto"

    from engine.api import create_app  # imported after the mode is set

    if args.openapi:
        app = create_app(start_background=False)
        out = Path(__file__).resolve().parent / "plugin" / "openapi.json"
        out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
        print("wrote", out)
        return

    import uvicorn

    mode = "LIVE (Binance Spot Testnet)" if args.live else "AUTO (live, falls back to REPLAY)" if args.auto else "REPLAY (recorded MOCK data)"
    print(f"\n  Centralized Trading Engine - {mode}\n  dashboard: http://localhost:{args.port}/\n  API menu:  http://localhost:{args.port}/docs\n")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    sys.exit(main())
