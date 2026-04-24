"""
Shared OHLCV cache daemon (Phase 0 PoC).

Listens on a Unix socket, accepts fetch/ping requests from freqtrade bots,
serves OHLCV data from an in-memory cache, and fetches from ccxt when needed.

Phase 0 scope:
  * Hyperliquid futures only (OHLCV + MARK + FUNDING_RATE supported as
    separate series but only lightly tested on FUTURES)
  * No partial-range merge: a cache entry is either fresh enough to serve
    (based on timeframe TTL) or we refetch
  * Token-bucket rate limit per exchange (shared across all bots)
  * Shutdown-on-idle after idle_daemon_shutdown_s with zero connections

Run directly:
    python -m freqtrade.ohlcv_cache.daemon --socket /tmp/ftcache-1000.sock

The client (OhlcvCacheClient) normally spawns this for you.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from freqtrade.ohlcv_cache.defaults import (
    EXCHANGE_DEFAULTS,
    resolve_exchange_config,
    resolve_global_config,
)
from freqtrade.ohlcv_cache.logger_setup import setup_daemon_logger
from freqtrade.ohlcv_cache.protocol import PROTOCOL_VERSION, dumps, loads_request


logger = logging.getLogger("ftcache.daemon")


# -------------------------------------------------------------------- token bucket


class TokenBucket:
    """Simple async token-bucket rate limiter shared across all clients."""

    def __init__(self, rate_per_s: float, burst: float):
        self.rate_per_s = rate_per_s
        self.burst = burst
        self.tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._backoff_until = 0.0
        self._backoff_factor = 1.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        effective_rate = self.rate_per_s / self._backoff_factor
        self.tokens = min(self.burst, self.tokens + elapsed * effective_rate)

    async def acquire(self, cost: float = 1.0) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                if now < self._backoff_until:
                    await asyncio.sleep(self._backoff_until - now)
                    continue
                self._refill()
                if self.tokens >= cost:
                    self.tokens -= cost
                    return
                effective_rate = self.rate_per_s / self._backoff_factor
                wait_s = (cost - self.tokens) / max(effective_rate, 0.001)
                await asyncio.sleep(wait_s)

    def trigger_backoff(self, duration_s: float = 60.0, factor: float = 2.0) -> None:
        self._backoff_factor = max(self._backoff_factor, factor)
        self._backoff_until = time.monotonic() + duration_s
        logger.warning(
            "rate-limit back-off triggered: factor=%.1fx for %.0fs",
            self._backoff_factor, duration_s,
        )

    def relax_backoff(self) -> None:
        if self._backoff_factor > 1.0:
            self._backoff_factor = max(1.0, self._backoff_factor / 2.0)


# -------------------------------------------------------------------- store


@dataclass
class CandleSeries:
    """Phase 0: store the full last-fetched OHLCV list + metadata.

    We do NOT do partial-range merging yet. Either the cache is fresh
    enough (last_fetch within one timeframe) and we reuse it, or we
    trigger a fetch.
    """
    exchange: str
    trading_mode: str
    pair: str
    timeframe: str
    candle_type: str
    data: list[list] = field(default_factory=list)
    drop_incomplete: bool = True
    last_fetch_monotonic: float = 0.0
    last_fetch_wall_ms: int = 0
    hits: int = 0
    misses: int = 0
    # Coalesce concurrent fetches for the exact same key+since
    _inflight: dict[tuple[int | None, int | None], asyncio.Future] = field(
        default_factory=dict, repr=False
    )


class CandleStore:
    def __init__(self) -> None:
        self._series: dict[tuple, CandleSeries] = {}

    def key(self, exchange: str, trading_mode: str, pair: str, timeframe: str, candle_type: str):
        return (exchange, trading_mode, pair, timeframe, candle_type)

    def get_or_create(
        self, exchange: str, trading_mode: str, pair: str, timeframe: str, candle_type: str
    ) -> CandleSeries:
        k = self.key(exchange, trading_mode, pair, timeframe, candle_type)
        s = self._series.get(k)
        if s is None:
            s = CandleSeries(
                exchange=exchange, trading_mode=trading_mode, pair=pair,
                timeframe=timeframe, candle_type=candle_type,
            )
            self._series[k] = s
        return s

    def all_series(self) -> list[CandleSeries]:
        return list(self._series.values())


# -------------------------------------------------------------------- ccxt client wrappers


class ExchangeFetcher:
    """Wraps a ccxt async client for one exchange+trading_mode combo."""

    def __init__(self, exchange: str, trading_mode: str, budget: TokenBucket):
        self.exchange = exchange
        self.trading_mode = trading_mode
        self.budget = budget
        self._client: Any = None
        self._lock = asyncio.Lock()

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is not None:
                return self._client
            import ccxt.async_support as ccxt_async  # lazy import
            if not hasattr(ccxt_async, self.exchange):
                raise RuntimeError(f"ccxt has no exchange '{self.exchange}'")
            config: dict[str, Any] = {"enableRateLimit": False}  # WE manage rate limit
            if self.trading_mode == "futures":
                config["options"] = {"defaultType": "swap"}
            self._client = getattr(ccxt_async, self.exchange)(config)
            logger.info(
                "initialised ccxt async client for %s (trading_mode=%s)",
                self.exchange, self.trading_mode,
            )
            return self._client

    async def fetch_ohlcv(
        self, pair: str, timeframe: str, since_ms: int | None,
        limit: int | None, candle_type: str,
    ) -> list[list]:
        client = await self._ensure_client()
        params: dict[str, Any] = {}
        if candle_type and candle_type not in ("spot", "futures"):
            params["price"] = candle_type
        await self.budget.acquire(1.0)
        try:
            data = await client.fetch_ohlcv(
                pair, timeframe=timeframe, since=since_ms, limit=limit, params=params,
            )
            return data
        except Exception as e:
            # Very light 429 detection — most ccxt classes raise RateLimitExceeded
            msg = str(e)
            if "429" in msg or "RateLimit" in e.__class__.__name__:
                self.budget.trigger_backoff(60.0, 2.0)
            raise

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass


# -------------------------------------------------------------------- session/server


@dataclass
class DaemonStats:
    started_monotonic: float = field(default_factory=time.monotonic)
    requests_total: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    active_clients: int = 0
    last_client_disconnect_monotonic: float | None = None

    def uptime_s(self) -> float:
        return time.monotonic() - self.started_monotonic


class Daemon:
    def __init__(
        self,
        socket_path: str,
        global_cfg: dict,
        exchange_overrides: dict[str, dict] | None = None,
    ) -> None:
        self.socket_path = socket_path
        self.global_cfg = global_cfg
        self.exchange_overrides = exchange_overrides or {}
        self.store = CandleStore()
        self.budgets: dict[str, TokenBucket] = {}
        self.fetchers: dict[tuple[str, str], ExchangeFetcher] = {}
        self.stats = DaemonStats()
        self._server: asyncio.base_events.Server | None = None
        self._shutdown_event = asyncio.Event()
        self._idle_shutdown_s = float(global_cfg.get("idle_daemon_shutdown_s", 60))

    # --------- helpers

    def _get_budget(self, exchange: str) -> TokenBucket:
        b = self.budgets.get(exchange)
        if b is None:
            ex_cfg = resolve_exchange_config(exchange, self.exchange_overrides.get(exchange))
            b = TokenBucket(
                rate_per_s=ex_cfg.get("rate_per_s", 5),
                burst=ex_cfg.get("burst", 10),
            )
            self.budgets[exchange] = b
        return b

    def _get_fetcher(self, exchange: str, trading_mode: str) -> ExchangeFetcher:
        k = (exchange, trading_mode)
        f = self.fetchers.get(k)
        if f is None:
            f = ExchangeFetcher(exchange, trading_mode, self._get_budget(exchange))
            self.fetchers[k] = f
        return f

    def _timeframe_to_seconds(self, tf: str) -> int:
        unit = tf[-1]
        n = int(tf[:-1])
        return n * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}.get(unit, 60)

    def _is_fresh(self, series: CandleSeries) -> bool:
        if not series.data:
            return False
        tf_s = self._timeframe_to_seconds(series.timeframe)
        age = time.monotonic() - series.last_fetch_monotonic
        # Fresh if refreshed within the last timeframe window
        return age < tf_s

    # --------- request handling

    async def _handle_fetch(self, req: dict) -> dict:
        t0 = time.monotonic()
        self.stats.requests_total += 1
        exchange = req["exchange"]
        trading_mode = req.get("trading_mode", "spot")
        pair = req["pair"]
        timeframe = req["timeframe"]
        candle_type = req.get("candle_type", "") or trading_mode
        since_ms = req.get("since_ms")
        limit = req.get("limit")

        # Phase 0: bypass cache for historic fetches (since_ms is not None).
        # Those paths (startup warmup, backtest) will be added in Phase 1
        # with partial-range merging.
        series = self.store.get_or_create(exchange, trading_mode, pair, timeframe, candle_type)

        if since_ms is None and self._is_fresh(series):
            series.hits += 1
            self.stats.cache_hits += 1
            return self._ok_response(req["req_id"], series, t0, served_from="cache")

        inflight_key = (since_ms, limit)
        fut = series._inflight.get(inflight_key)
        if fut is not None:
            await fut
            if since_ms is None and self._is_fresh(series):
                series.hits += 1
                self.stats.cache_hits += 1
                return self._ok_response(
                    req["req_id"], series, t0, served_from="coalesced"
                )

        if inflight_key not in series._inflight:
            fut = asyncio.get_running_loop().create_future()
            # Always acknowledge the future's result to silence asyncio's
            # "Future exception was never retrieved" warning. Waiters that
            # await this future don't care about the exception object —
            # they check cache freshness themselves and re-initiate when needed.
            fut.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
            series._inflight[inflight_key] = fut
            try:
                fetcher = self._get_fetcher(exchange, trading_mode)
                data = await fetcher.fetch_ohlcv(
                    pair=pair, timeframe=timeframe, since_ms=since_ms,
                    limit=limit, candle_type=candle_type,
                )
                # Keep only if this was a live refresh (since_ms=None).
                # Historic fetches (since_ms!=None) are returned direct without caching
                # in Phase 0.
                if since_ms is None:
                    # Never cache an empty response: it would poison the cache
                    # and starve the strategy on subsequent "hits" until the
                    # timeframe TTL expires. Return the empty payload to the
                    # caller (it'll log "Empty candle") but don't update
                    # last_fetch_monotonic so the next call retries immediately.
                    if data:
                        series.data = data
                        series.last_fetch_monotonic = time.monotonic()
                        series.last_fetch_wall_ms = int(time.time() * 1000)
                        series.drop_incomplete = True
                    series.misses += 1
                    self.stats.cache_misses += 1
                    fut.set_result(None)
                    if data:
                        return self._ok_response(
                            req["req_id"], series, t0, served_from="fetch"
                        )
                    else:
                        logger.warning(
                            "empty OHLCV response for %s %s %s — not caching",
                            pair, timeframe, candle_type,
                        )
                        return {
                            "req_id": req["req_id"], "ok": True,
                            "pair": pair, "timeframe": timeframe,
                            "candle_type": candle_type,
                            "data": [], "drop_incomplete": True,
                            "served_from": "empty_uncached",
                            "latency_ms": (time.monotonic() - t0) * 1000,
                        }
                else:
                    fut.set_result(None)
                    return {
                        "req_id": req["req_id"], "ok": True,
                        "pair": pair, "timeframe": timeframe,
                        "candle_type": candle_type,
                        "data": data, "drop_incomplete": True,
                        "served_from": "fetch_direct",
                        "latency_ms": (time.monotonic() - t0) * 1000,
                    }
            except Exception as e:
                # Signal completion to waiters without propagating the
                # exception via the future. They will re-check cache
                # freshness and re-initiate the fetch themselves if needed.
                if not fut.done():
                    fut.set_result(None)
                raise
            finally:
                series._inflight.pop(inflight_key, None)

        # Shouldn't reach here
        return {
            "req_id": req["req_id"], "ok": False,
            "error_type": "LogicError",
            "error_message": "Inflight coalescing fallthrough",
        }

    def _ok_response(
        self, req_id: str, series: CandleSeries, t0: float, served_from: str,
    ) -> dict:
        return {
            "req_id": req_id, "ok": True,
            "pair": series.pair, "timeframe": series.timeframe,
            "candle_type": series.candle_type,
            "data": series.data, "drop_incomplete": series.drop_incomplete,
            "served_from": served_from,
            "latency_ms": (time.monotonic() - t0) * 1000,
        }

    async def _dispatch(self, req: dict) -> dict:
        op = req.get("op", "fetch")
        if op == "ping":
            return {
                "req_id": req.get("req_id", ""),
                "ok": True,
                "daemon_version": PROTOCOL_VERSION,
                "uptime_s": self.stats.uptime_s(),
            }
        if op == "stats":
            return {
                "req_id": req.get("req_id", ""),
                "ok": True,
                "uptime_s": self.stats.uptime_s(),
                "active_clients": self.stats.active_clients,
                "requests_total": self.stats.requests_total,
                "cache_hits": self.stats.cache_hits,
                "cache_misses": self.stats.cache_misses,
                "series_count": len(self.store.all_series()),
            }
        if op == "fetch":
            try:
                return await self._handle_fetch(req)
            except Exception as e:
                logger.exception("fetch failed: %s", e)
                return {
                    "req_id": req.get("req_id", ""),
                    "ok": False,
                    "error_type": e.__class__.__name__,
                    "error_message": str(e),
                }
        return {
            "req_id": req.get("req_id", ""),
            "ok": False,
            "error_type": "UnknownOp",
            "error_message": f"Unknown op: {op}",
        }

    # --------- server

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        self.stats.active_clients += 1
        peer = writer.get_extra_info("peername") or "unix"
        logger.info("client connected (%s) — active=%d", peer, self.stats.active_clients)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    req = loads_request(line)
                except Exception as e:
                    logger.warning("bad json from client: %s", e)
                    continue
                resp = await self._dispatch(req)
                try:
                    writer.write(dumps(resp))
                    await writer.drain()
                except ConnectionResetError:
                    break
        finally:
            self.stats.active_clients -= 1
            self.stats.last_client_disconnect_monotonic = time.monotonic()
            logger.info(
                "client disconnected — active=%d", self.stats.active_clients,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _idle_watchdog(self) -> None:
        while not self._shutdown_event.is_set():
            await asyncio.sleep(5)
            if self.stats.active_clients > 0:
                continue
            if self.stats.last_client_disconnect_monotonic is None:
                # Never had a client; use startup time as anchor
                idle_s = self.stats.uptime_s()
            else:
                idle_s = time.monotonic() - self.stats.last_client_disconnect_monotonic
            if idle_s >= self._idle_shutdown_s:
                logger.info(
                    "idle for %.0fs (threshold %.0fs) — shutting down",
                    idle_s, self._idle_shutdown_s,
                )
                self._shutdown_event.set()
                return

    async def serve(self) -> None:
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

        # Raise the default StreamReader buffer from 64KB so large OHLCV
        # JSON payloads (500–5000 candles) don't overrun readline().
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=self.socket_path,
            limit=16 * 1024 * 1024,
        )
        os.chmod(self.socket_path, 0o600)
        logger.info(
            "daemon listening on %s (pid=%d, proto=%d)",
            self.socket_path, os.getpid(), PROTOCOL_VERSION,
        )

        watchdog_task = asyncio.create_task(self._idle_watchdog())

        try:
            await self._shutdown_event.wait()
        finally:
            watchdog_task.cancel()
            self._server.close()
            await self._server.wait_closed()
            for f in list(self.fetchers.values()):
                await f.close()
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
            logger.info("daemon stopped cleanly")

    def request_shutdown(self) -> None:
        self._shutdown_event.set()


# -------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=False)
    parser.add_argument("--config", required=False,
                        help="JSON string with global+exchanges overrides")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    raw_cfg: dict = {}
    if args.config:
        try:
            raw_cfg = json.loads(args.config)
        except Exception as e:
            print(f"bad --config JSON: {e}", file=sys.stderr)
            return 2

    global_cfg = resolve_global_config(raw_cfg.get("global") if raw_cfg else None)
    if args.socket:
        global_cfg["socket_path"] = args.socket

    setup_daemon_logger(global_cfg.get("log_path"), level=args.log_level)
    logger.info(
        "starting ftcache daemon — socket=%s log=%s",
        global_cfg["socket_path"], global_cfg.get("log_path"),
    )

    exchange_overrides = raw_cfg.get("exchanges") if raw_cfg else None
    daemon = Daemon(
        socket_path=global_cfg["socket_path"],
        global_cfg=global_cfg,
        exchange_overrides=exchange_overrides,
    )

    def _sig_handler(*_):
        logger.info("signal received — requesting shutdown")
        daemon.request_shutdown()

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    try:
        asyncio.run(daemon.serve())
    except Exception as e:
        logger.exception("daemon crashed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
