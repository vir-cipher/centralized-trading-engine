# Demo night: how the pieces come together (for anyone, no coding needed)

## What runs where
- **One laptop runs everything.** One command, `python run.py --live`, starts the engine. The listener, belt, clerk, ledger, advice and API all run inside that one program.
- **The browser on the same laptop** shows the dashboard at `http://localhost:8000` and the API menu at `/docs`.
- **Binance Spot Testnet** sends trades in and receives our signed orders.
- **The other team's plugin** calls our API with its key.

## The 5-minute demo, in order
| Minute | Show | Say |
|---|---|---|
| 0–1 | The dashboard with the LIVE badge and the price line moving | "We listen to Binance Testnet and clean every trade into SQLite." |
| 1–2 | `/health`: trades stored and the bin counts | "Broken and repeated messages are rejected and counted." |
| 2–3 | The advice card and the honest-test line | "Two averages give BUY, SELL or HOLD. It is advice only. We test it honestly against a baseline." |
| 3–4 | Place a small MARKET order, then a LIMIT order, then cancel the LIMIT | "Every order is signed with HMAC-SHA256. The secret never leaves this laptop." |
| 4–5 | `/docs`, then the other team's plugin calling us | "This is our published API. Another team builds on it." |

## If Binance or the Wi-Fi is down
1. Stop the program (Ctrl+C).
2. Run `python run.py`.

The same pipes now play the recorded file. The badge says **REPLAY**. The course allows deferred-live data, and we say so openly.

## Checklist the night before
- [ ] `python -m pytest -q` is all green.
- [ ] `.env` has the Testnet keys; `python run.py --live` shows the LIVE badge.
- [ ] One test order placed and cancelled on Testnet.
- [ ] The laptop clock is synced (a drifted clock gives error -1021).
- [ ] The other team has run their plugin against our REPLAY mode.
