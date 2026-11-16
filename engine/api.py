"""The front desk: a FastAPI web API that people and other teams' plugins call (APP + DEV).

In plain words:
    Everything so far happens inside the laptop. This file opens a door
    with a menu. Anyone (our dashboard, another team's plugin, a teacher with a
    browser) can ask questions like "what is the price of BTCUSDT?" or place an
    order, by visiting an address such as  http://localhost:8000/prices/BTCUSDT.

    FastAPI writes the menu by itself at  /docs  (a "Swagger" page), using the
    descriptions and examples in this file. That menu is what the other team
    reads to build their plugin.

Start-up and shut-down ("lifespan"):
    When the server starts, it opens the database, starts the listener (LIVE)
    or the replayer (REPLAY), and starts the clerk. When it stops, it tells
    them to stop and closes the database. One program, one laptop.

Rules for callers:
    - reading (GET) is open to everyone
    - writing (POST /orders, DELETE /orders/{id}) needs a plugin key in the
      X-API-Key header, so a random web page cannot place orders
    - every error comes back in ONE shape:  {"error": {"code": ..., "message": ...}}
"""

import asyncio
import contextlib
import logging
import time
import uuid
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, store, trace
from .exchange import ExchangeError, FakeExchange, TestnetExchange
from .pipeline import Pipeline
from .signals import crossover_signal, honest_test
from .sources import listen_live, replay_file

API_VERSION = "1.1.0"
log = logging.getLogger("cte.api")


# ---------- shapes of the data we send and receive (the contract other teams rely on) ----------

class Price(BaseModel):
    symbol: str = Field(examples=["BTCUSDT"])
    price: float = Field(examples=[67012.5], description="latest known price")
    ts: Optional[int] = Field(None, examples=[1795301234567], description="time of that price, ms since 1970 UTC")
    source: str = Field(examples=["REPLAY"], description="LIVE (Binance Testnet) or REPLAY (recorded data)")


class Candle(BaseModel):
    minute_start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class Trade(BaseModel):
    symbol: str
    trade_id: int
    price: float
    qty: float
    ts: int
    source: str


class Signal(BaseModel):
    symbol: str = Field(examples=["BTCUSDT"])
    advice: Literal["BUY", "SELL", "HOLD"] = Field(examples=["HOLD"])
    reason: str = Field(examples=["no fresh crossing this minute"])
    short_now: Optional[float] = None
    long_now: Optional[float] = None
    short_window: int = Field(examples=[5])
    long_window: int = Field(examples=[15])
    honest_test: dict = Field(description="rule vs baseline accuracy on later minutes only")
    advisory_only: bool = Field(True, description="the engine never places an order by itself")


class OrderIn(BaseModel):
    symbol: str = Field(examples=["BTCUSDT"])
    side: Literal["BUY", "SELL"] = Field(examples=["BUY"])
    type: Literal["MARKET", "LIMIT"] = Field(examples=["MARKET"])
    qty: float = Field(gt=0, examples=[0.001])
    price: Optional[float] = Field(None, gt=0, description="required for LIMIT, ignored for MARKET")


class Order(BaseModel):
    id: int
    client_id: str
    symbol: str
    side: str
    type: str
    qty: float
    price: Optional[float]
    status: str = Field(examples=["FILLED"], description="NEW, FILLED, PARTIALLY_FILLED, CANCELED, REJECTED")
    exchange_id: Optional[str]
    filled_price: Optional[float]
    created_ms: int
    note: Optional[str]


class Balance(BaseModel):
    asset: str
    free: float
    locked: float


class ErrorBody(BaseModel):
    code: str = Field(examples=["NOT_FOUND"])
    message: str = Field(examples=["no data yet for ETHUSDT"])


class ErrorOut(BaseModel):
    error: ErrorBody


ERRORS = {400: {"model": ErrorOut}, 401: {"model": ErrorOut}, 404: {"model": ErrorOut}, 502: {"model": ErrorOut}}


class ApiError(Exception):
    """Raise this anywhere in a route to send the one-shape error back."""

    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class NoKeysExchange:
    """LIVE without keys: listening works (prices are public), orders politely refuse."""

    def _no(self, *a, **k):
        raise ExchangeError("KEYS_MISSING", "add BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET to .env")

    place_order = cancel_order = balances = _no


# ---------- AUTO mode: try LIVE, fall back to REPLAY by itself ----------

async def auto_source(pipe, replay_path, stop, tasks, wait_s=15):
    """Demo-night safety net.

    In plain words:
        Start listening to Binance. If not a single message arrives within
        15 seconds (Wi-Fi down, Testnet down), stop waiting and play the
        recording instead. The dashboard badge flips to REPLAY, so nobody is
        misled. The same belt, clerk, ledger and API keep working.
    """
    live = asyncio.create_task(listen_live(pipe.queue, config.STREAM_URL, config.SYMBOLS, stop))
    tasks.append(live)
    for _ in range(wait_s * 10):
        if pipe.mode == "LIVE" and pipe.stored > 0 or pipe.queue.qsize() > 0:
            log.info("AUTO: live data is flowing")
            return
        await asyncio.sleep(0.1)
    log.warning("AUTO: no live data in %s s, switching to REPLAY", wait_s)
    live.cancel()
    pipe.mode = "REPLAY"
    await replay_file(pipe.queue, replay_path, config.REPLAY_SPEED, stop)


# ---------- the app ----------

def create_app(mode=None, db_path=None, exchange=None, start_background=True, replay_file_path=None):
    """Build the whole app. Tests call this with their own database and a FakeExchange."""
    mode = (mode or config.MODE).lower()
    state = {}

    @contextlib.asynccontextmanager
    async def lifespan(app):
        # ---- start-up ----
        db = store.connect(db_path or config.DB_PATH)
        pipe = Pipeline(db)
        pipe.mode = "LIVE" if mode in ("live", "auto") else "REPLAY"
        ex = exchange
        if ex is None:
            if mode == "live" and config.API_KEY and config.API_SECRET:
                ex = TestnetExchange(config.REST_URL, config.API_KEY, config.API_SECRET, config.RECV_WINDOW)
            elif mode == "live":
                ex = NoKeysExchange()     # prices still flow; orders explain what is missing
            else:
                ex = FakeExchange(pipe.last_price)
        state.update(db=db, pipe=pipe, exchange=ex)
        app.state.pipe = pipe   # lets tests feed messages straight in
        stop, tasks = asyncio.Event(), []
        if start_background:
            replay_path = replay_file_path or config.REPLAY_FILE
            if mode == "live":
                tasks.append(asyncio.create_task(listen_live(pipe.queue, config.STREAM_URL, config.SYMBOLS, stop)))
            elif mode == "auto":
                tasks.append(asyncio.create_task(auto_source(pipe, replay_path, stop, tasks)))
            else:
                tasks.append(asyncio.create_task(replay_file(pipe.queue, replay_path, config.REPLAY_SPEED, stop)))
            tasks.append(asyncio.create_task(pipe.run(stop)))
        yield
        # ---- shut-down: stop the listener and the clerk, close the file ----
        stop.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        db.close()

    app = FastAPI(
        title="Centralized Trading Engine",
        version=API_VERSION,
        lifespan=lifespan,
        description=(
            "A gateway to the Binance Spot Testnet (practice market, toy money). "
            "It listens to live trades, cleans them, stores them, gives BUY/SELL/HOLD advice "
            "from two moving averages, and forwards signed orders.\n\n"
            "**Reading is open. Placing or cancelling an order needs `X-API-Key`.**\n\n"
            "Every error has the shape `{\"error\": {\"code\", \"message\"}}`. "
            "Guide for plugin builders: `plugin/INTEGRATE_IN_15_MIN.md` in the repository."
        ),
    )
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    # ---- the engine's own call log (see engine/trace.py) ----
    @app.middleware("http")
    async def _trace_requests(request: Request, call_next):
        """Write one line per API call: method, path, status, time taken.

        Static files (the dashboard itself) and the log reader /trace are skipped,
        so the log shows only real API calls. The key is printed as ****.
        """
        t0 = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        quiet = path == "/trace" or path.startswith("/docs") or path == "/openapi.json" or "." in path.rsplit("/", 1)[-1] or path == "/"
        if not quiet:
            q = ("?" + request.url.query) if request.url.query else ""
            key = "  key=****" if request.headers.get("x-api-key") else ""
            ms = round((time.perf_counter() - t0) * 1000)
            trace.log("in", f"{request.method:<6} {path}{q}{key}  -> {response.status_code}  {ms} ms")
        # Lets a page on https://ansh-bhargav.web.app talk to an engine on this laptop (localhost).
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "HTTP_" + str(exc.status_code), "message": str(exc.detail)}})

    # Why "async def" on every route below?
    # The listener, the clerk and these routes all run on ONE thread (the event
    # loop), taking turns. SQLite connections must not be shared across threads,
    # and taking turns on one thread means a half-written row is never read.

    def need_key(x_api_key: Optional[str] = Header(None, description="plugin key, required for orders")):
        """Writing routes call this first. No key, or a wrong key -> 401."""
        if x_api_key not in config.PLUGIN_KEYS:
            raise ApiError(401, "BAD_API_KEY", "send a valid X-API-Key header to place or cancel orders")

    def pipe():
        return state["pipe"]

    # ---- reading ----

    @app.get("/trace", tags=["status"], summary="The engine's own call log: newest lines after `after`")
    async def get_trace(after: int = 0):
        """Lines like a terminal: every API call in, every Binance call out. Secrets are masked."""
        return trace.since(after)

    @app.get("/health", tags=["status"], summary="Is the engine running, and in which mode?")
    async def health():
        p = pipe()
        return {"ok": True, "mode": p.mode, "trades_stored": p.stored, "rejected": p.rejected(), "version": API_VERSION}

    @app.get("/prices/{symbol}", response_model=Price, responses=ERRORS, tags=["market"], summary="Latest price of one symbol")
    async def get_price(symbol: str):
        symbol, p = symbol.upper(), pipe()
        if symbol in p.latest:
            return {"symbol": symbol, **p.latest[symbol]}
        row = store.last_trade(state["db"], symbol)
        if not row:
            raise ApiError(404, "NOT_FOUND", "no data yet for " + symbol)
        return {"symbol": symbol, "price": row["price"], "ts": row["ts"], "source": row["source"]}

    @app.get("/trades", response_model=List[Trade], tags=["market"], summary="Most recent clean trades")
    async def get_trades(symbol: str = Query("BTCUSDT"), limit: int = Query(20, ge=1, le=500)):
        return store.recent_trades(state["db"], symbol.upper(), limit)

    @app.get("/candles", response_model=List[Candle], tags=["market"], summary="One-minute candles, oldest first")
    async def get_candles(symbol: str = Query("BTCUSDT"), limit: int = Query(60, ge=1, le=1440)):
        return store.minute_candles(state["db"], symbol.upper(), limit)

    @app.get("/signals/{symbol}", response_model=Signal, tags=["signal"], summary="BUY / SELL / HOLD advice (advisory only)")
    async def get_signal(symbol: str):
        symbol = symbol.upper()
        closes = [c["close"] for c in store.minute_candles(state["db"], symbol, 1440)]
        s = crossover_signal(closes, config.SHORT_WINDOW, config.LONG_WINDOW)
        return {"symbol": symbol, **s, "short_window": config.SHORT_WINDOW, "long_window": config.LONG_WINDOW,
                "honest_test": honest_test(closes, config.SHORT_WINDOW, config.LONG_WINDOW), "advisory_only": True}

    @app.get("/account/balance", response_model=List[Balance], responses=ERRORS, tags=["account"], summary="Testnet balances (toy money)")
    async def get_balance():
        try:
            return state["exchange"].balances()
        except ExchangeError as e:
            raise ApiError(502, "EXCHANGE_" + str(e.code), e.message)

    @app.get("/orders", response_model=List[Order], tags=["orders"], summary="Orders placed through this engine")
    async def get_orders(symbol: Optional[str] = None, limit: int = Query(50, ge=1, le=500)):
        return store.list_orders(state["db"], symbol.upper() if symbol else None, limit)

    # ---- writing (needs X-API-Key) ----

    @app.post("/orders", response_model=Order, responses=ERRORS, tags=["orders"], dependencies=[Depends(need_key)],
              summary="Place a MARKET or LIMIT order (signed with HMAC-SHA256 before it leaves the laptop)")
    async def post_order(order: OrderIn):
        if order.type == "LIMIT" and order.price is None:
            raise ApiError(400, "PRICE_REQUIRED", "a LIMIT order needs a price")
        db = state["db"]
        client_id = "cte-" + uuid.uuid4().hex[:12]
        oid = store.save_order(db, {"client_id": client_id, "symbol": order.symbol.upper(), "side": order.side,
                                    "type": order.type, "qty": order.qty,
                                    "price": order.price if order.type == "LIMIT" else None, "status": "PENDING"})
        try:
            result = state["exchange"].place_order(client_id, order.symbol.upper(), order.side, order.type, order.qty, order.price)
            store.update_order(db, oid, **result)
        except ExchangeError as e:
            store.update_order(db, oid, status="REJECTED", note=f"{e.code}: {e.message}")
            raise ApiError(502, "EXCHANGE_" + str(e.code), e.message)
        return store.get_order(db, oid)

    @app.delete("/orders/{order_id}", response_model=Order, responses=ERRORS, tags=["orders"], dependencies=[Depends(need_key)],
                summary="Cancel an order that is still open (NEW). Cancelling does not undo a fill.")
    async def delete_order(order_id: int):
        db = state["db"]
        o = store.get_order(db, order_id)
        if not o:
            raise ApiError(404, "NOT_FOUND", f"no order {order_id}")
        if o["status"] not in ("NEW", "PARTIALLY_FILLED"):
            raise ApiError(400, "NOT_OPEN", f"order {order_id} is {o['status']}; only open orders can be cancelled")
        try:
            result = state["exchange"].cancel_order(o["client_id"], o["symbol"])
        except ExchangeError as e:
            raise ApiError(502, "EXCHANGE_" + str(e.code), e.message)
        store.update_order(db, order_id, status=result["status"])
        return store.get_order(db, order_id)

    # ---- the dashboard, served from the same address ----
    dash = Path(__file__).resolve().parent.parent / "dashboard"
    if dash.exists():
        app.mount("/", StaticFiles(directory=str(dash), html=True), name="dashboard")

    return app
