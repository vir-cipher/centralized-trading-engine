# Backlog (ideas for later, not built yet)

## Epic: full portfolio ledger
Today the dashboard works out gain or loss from the order list only (see `dashboard/app.js`, `showPortfolio`). That is enough for the demo and easy to explain.

A full version would add:
- a `ledger` table in SQLite: a saved starting balance (the baseline) and its value on day 1;
- the pretend exchange rebuilding its balances from the saved orders when the engine restarts;
- a `GET /portfolio` route: baseline value, value now, net change, and "if we had just held" (trading effect vs price effect);
- a chart of portfolio value over time.

Why not now: three files change and about 120 lines, for something the course does not grade. Revisit after the end-sem.
