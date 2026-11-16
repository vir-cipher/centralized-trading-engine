"""Settings for the whole engine, read once at start-up.

In plain words:
    This file is the engine's settings card. Things that change between
    laptops (keys, which coins to watch, where the database file lives) are
    read from a hidden file called `.env`, so they never end up inside the
    code or on GitHub.

Why a `.env` file?
    The Binance secret key is like the PIN of a bank card. If it is written
    inside the code and pushed to GitHub, anyone can read it. `.env` is listed
    in `.gitignore`, so git never uploads it. `.env.example` shows the shape
    without the real values.
"""

import os
from pathlib import Path

try:
    # python-dotenv copies the lines of `.env` into the environment.
    # If it is not installed, the engine still runs with plain environment variables.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - optional helper
    pass

ROOT = Path(__file__).resolve().parent.parent

# --- Binance Spot Testnet: the practice market (fake money, its own prices) ---
STREAM_URL = os.getenv("CTE_STREAM_URL", "wss://stream.testnet.binance.vision/stream")
REST_URL = os.getenv("CTE_REST_URL", "https://testnet.binance.vision/api")
API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")

# Which coin pairs to listen to. "BTCUSDT" means: Bitcoin priced in USDT.
SYMBOLS = [s.strip().upper() for s in os.getenv("CTE_SYMBOLS", "BTCUSDT").split(",") if s.strip()]

# --- Storage ---
DB_PATH = Path(os.getenv("CTE_DB_PATH", str(ROOT / "data" / "engine.sqlite3")))

# --- Mode ---
# "replay": play a recorded file through the same pipes (no internet needed).
# "live":   listen to Binance Testnet for real.
MODE = os.getenv("CTE_MODE", "replay").lower()
REPLAY_FILE = Path(os.getenv("CTE_REPLAY_FILE", str(ROOT / "data" / "replay" / "btcusdt_mock.jsonl")))
REPLAY_SPEED = float(os.getenv("CTE_REPLAY_SPEED", "20"))  # 20 = twenty times faster than real time

# --- Signal windows (the two averages) ---
SHORT_WINDOW = int(os.getenv("CTE_SHORT_WINDOW", "5"))   # minutes
LONG_WINDOW = int(os.getenv("CTE_LONG_WINDOW", "15"))    # minutes

# --- Who may place orders through our API (other teams' plugins) ---
# A comma-separated list of keys. A caller sends one of them in the X-API-Key header.
PLUGIN_KEYS = {k.strip() for k in os.getenv("CTE_PLUGIN_KEYS", "demo-plugin-key").split(",") if k.strip()}

# Web pages allowed to call the API from a browser (CORS). "*" means any page.
CORS_ORIGINS = [o.strip() for o in os.getenv("CTE_CORS_ORIGINS", "*").split(",") if o.strip()]

# Binance accepts a signed request only if its time stamp is this fresh (milliseconds).
RECV_WINDOW = int(os.getenv("CTE_RECV_WINDOW", "5000"))
