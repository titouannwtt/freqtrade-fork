"""
Client for the shared OHLCV cache daemon.

Exposes an `OhlcvCacheClient` used by `CachedExchangeMixin`. Handles:
  * async connection to the Unix socket (JSON newline protocol)
  * auto-spawn of the daemon via subprocess.Popen if no daemon is running
  * graceful fallback when the daemon is unreachable

The caller is responsible for calling `.fetch()` from an asyncio context
(freqtrade's Exchange loop).
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from freqtrade.enums import CandleType
from freqtrade.ohlcv_cache.defaults import (
    EXCHANGE_DEFAULTS,
    default_log_dir,
    resolve_global_config,
)
from freqtrade.ohlcv_cache.logger_setup import get_client_logger
from freqtrade.ohlcv_cache.protocol import dumps, loads_response


logger = get_client_logger()


class CacheUnavailable(RuntimeError):
    """Raised when the cache daemon is unreachable and fallback is needed."""


# Process-wide cache of clients to avoid spawning multiple daemons within one bot
_CLIENT_SINGLETONS: dict[str, "OhlcvCacheClient"] = {}


class OhlcvCacheClient:
    def __init__(
        self,
        socket_path: str,
        timeout_s: float = 10.0,
        exchange_id: str = "",
        trading_mode: str = "spot",
        respawn_cfg: dict | None = None,
    ) -> None:
        self.socket_path = socket_path
        self.timeout_s = timeout_s
        self.exchange_id = exchange_id
        self.trading_mode = trading_mode
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        # Cached parameters needed to respawn the daemon if it has died.
        # Populated by get_or_spawn().
        self._respawn_cfg: dict | None = respawn_cfg

    # ---------------- connection lifecycle

    async def _connect(self) -> None:
        # 16 MB reader buffer: a 5000-candle JSON response can exceed 400 KB,
        # well past asyncio's 64 KB readline() default which raises
        # LimitOverrunError silently and poisons the bot's _klines cache.
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_unix_connection(
                self.socket_path, limit=16 * 1024 * 1024,
            ),
            timeout=self.timeout_s,
        )

    async def _ensure_connected(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        try:
            await self._connect()
            return
        except (FileNotFoundError, ConnectionRefusedError, asyncio.TimeoutError) as e:
            first_err = e

        # Daemon socket missing — try to respawn once if we have the info.
        if self._respawn_cfg is None:
            raise CacheUnavailable(f"cannot connect to daemon: {first_err}") from first_err
        try:
            logger.info("daemon socket missing, attempting respawn")
            _ensure_daemon_running(**self._respawn_cfg)
            await self._connect()
        except (FileNotFoundError, ConnectionRefusedError, asyncio.TimeoutError) as e:
            raise CacheUnavailable(
                f"cannot connect to daemon after respawn: {e}"
            ) from e
        except CacheUnavailable:
            raise

    async def close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    # ---------------- request/response

    async def _send_and_receive(self, payload: dict) -> dict:
        async with self._lock:
            await self._ensure_connected()
            assert self._writer is not None and self._reader is not None
            try:
                self._writer.write(dumps(payload))
                await self._writer.drain()
                line = await asyncio.wait_for(
                    self._reader.readline(), timeout=self.timeout_s,
                )
                if not line:
                    raise CacheUnavailable("daemon closed connection")
                return loads_response(line)
            except (
                ConnectionError, asyncio.TimeoutError, BrokenPipeError,
                ValueError, EOFError,
            ) as e:
                # ValueError here typically means LimitOverrunError from
                # readline(); treat it as an i/o failure rather than letting
                # it silently kill the bot's dataframe refresh.
                # str(asyncio.TimeoutError()) is empty, so include the
                # exception class name for diagnostic clarity in logs.
                await self.close()
                raise CacheUnavailable(
                    f"i/o error with daemon: {e.__class__.__name__}: {e}"
                ) from e

    async def ping(self) -> dict:
        return await self._send_and_receive({"op": "ping", "req_id": uuid.uuid4().hex})

    async def fetch(
        self, pair: str, timeframe: str,
        candle_type: CandleType | str, since_ms: int | None,
        limit: int | None,
    ) -> tuple[str, str, CandleType, list, bool]:
        """Return an OHLCVResponse compatible with
        freqtrade.exchange.exchange.Exchange._async_get_candle_history."""
        ct_str = candle_type.value if isinstance(candle_type, CandleType) else str(candle_type)
        req = {
            "op": "fetch",
            "req_id": uuid.uuid4().hex,
            "exchange": self.exchange_id,
            "trading_mode": self.trading_mode,
            "pair": pair,
            "timeframe": timeframe,
            "candle_type": ct_str,
            "since_ms": since_ms,
            "limit": limit,
        }
        resp = await self._send_and_receive(req)
        if not resp.get("ok"):
            raise CacheUnavailable(
                f"daemon error: {resp.get('error_type')} {resp.get('error_message')}"
            )
        try:
            ct_ret = CandleType(resp["candle_type"])
        except ValueError:
            ct_ret = CandleType.SPOT
        return (
            resp["pair"], resp["timeframe"], ct_ret,
            resp.get("data", []), resp.get("drop_incomplete", True),
        )

    # ---------------- spawn-on-demand

    @classmethod
    def get_or_spawn(
        cls, exchange_id: str, trading_mode: str, bot_config: dict,
    ) -> "OhlcvCacheClient":
        """Return a process-wide singleton client for (exchange_id, trading_mode),
        spawning the daemon if necessary."""
        cache_cfg = bot_config.get("shared_ohlcv_cache") or {}
        global_cfg = resolve_global_config({
            k: v for k, v in cache_cfg.items()
            if k in {
                "socket_path", "lock_path", "log_path",
                "idle_daemon_shutdown_s", "client_timeout_s",
                "client_spawn_timeout_s",
            }
        })
        socket_path = global_cfg["socket_path"]

        key = f"{exchange_id}:{trading_mode}:{socket_path}"
        existing = _CLIENT_SINGLETONS.get(key)
        if existing is not None:
            return existing

        respawn_cfg = {
            "socket_path": socket_path,
            "lock_path": global_cfg["lock_path"],
            "log_path": global_cfg["log_path"],
            "spawn_timeout_s": global_cfg["client_spawn_timeout_s"],
            "daemon_config": {
                "global": {
                    "idle_daemon_shutdown_s": global_cfg["idle_daemon_shutdown_s"],
                    "log_path": global_cfg["log_path"],
                },
                "exchanges": cache_cfg.get("exchanges") or {},
            },
        }
        _ensure_daemon_running(**respawn_cfg)
        client = cls(
            socket_path=socket_path,
            timeout_s=float(global_cfg["client_timeout_s"]),
            exchange_id=exchange_id,
            trading_mode=trading_mode,
            respawn_cfg=respawn_cfg,
        )
        _CLIENT_SINGLETONS[key] = client
        logger.info("client configured for %s/%s via %s",
                    exchange_id, trading_mode, socket_path)
        return client


# ---------------- spawn helpers (module-level, sync)


def _is_socket_live(socket_path: str, timeout_s: float = 1.0) -> bool:
    import socket
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout_s)
    try:
        s.connect(socket_path)
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, OSError):
        return False
    else:
        return True
    finally:
        try:
            s.close()
        except Exception:
            pass


def _ensure_daemon_running(
    socket_path: str,
    lock_path: str,
    log_path: str,
    spawn_timeout_s: float,
    daemon_config: dict,
) -> None:
    """Fast-path check → flock acquire → subprocess.Popen → poll socket.

    Raises CacheUnavailable if the daemon cannot be started in time.
    """
    if _is_socket_live(socket_path):
        return

    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    default_log_dir().mkdir(parents=True, exist_ok=True)

    lock_fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another bot is spawning — wait for socket to appear
            deadline = time.monotonic() + spawn_timeout_s
            while time.monotonic() < deadline:
                if _is_socket_live(socket_path):
                    return
                time.sleep(0.2)
            raise CacheUnavailable("timed out waiting for concurrent daemon spawn")

        # We hold the lock. Re-check in case a recent spawn completed.
        if _is_socket_live(socket_path):
            return

        logger.info("spawning ftcache daemon (socket=%s)", socket_path)
        log_f = open(log_path, "ab", buffering=0)
        try:
            subprocess.Popen(
                [
                    sys.executable, "-m", "freqtrade.ohlcv_cache.daemon",
                    "--socket", socket_path,
                    "--config", json.dumps(daemon_config),
                    "--log-level", "INFO",
                ],
                stdin=subprocess.DEVNULL,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            log_f.close()

        # Poll for readiness
        deadline = time.monotonic() + spawn_timeout_s
        while time.monotonic() < deadline:
            if _is_socket_live(socket_path):
                logger.info("daemon is up on %s", socket_path)
                return
            time.sleep(0.2)
        raise CacheUnavailable(
            f"daemon did not become ready within {spawn_timeout_s}s (see {log_path})"
        )
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(lock_fd)
        except Exception:
            pass
