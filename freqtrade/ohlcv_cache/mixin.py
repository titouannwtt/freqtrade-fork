"""
CachedExchangeMixin: overrides Exchange._async_get_candle_history to
delegate OHLCV fetches to the shared ftcache daemon.

Phase 0 scope: only caches live fetches (since_ms=None). Historic
fetches (startup warmup, backtest) are delegated directly to ccxt for
now; Phase 1 will extend partial-range merging to those paths.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from freqtrade.enums import CandleType
from freqtrade.ohlcv_cache.client import CacheUnavailable, OhlcvCacheClient


if TYPE_CHECKING:
    from freqtrade.exchange.exchange_types import OHLCVResponse


logger = logging.getLogger("ftcache.client")


class CachedExchangeMixin:
    """Mixin intended to sit before Exchange in the MRO.

    When `shared_ohlcv_cache.enabled` is not explicitly False, live OHLCV
    requests (since_ms=None) are routed through the ftcache daemon.
    Historic requests and error paths fall through to the native
    Exchange implementation (which preserves @retrier_async).
    """

    _ftcache_client: Any = None  # OhlcvCacheClient | False sentinel
    _ftcache_warned: bool = False

    def _ftcache_enabled(self) -> bool:
        cfg = self._config.get("shared_ohlcv_cache")  # type: ignore[attr-defined]
        if cfg is None:
            return True  # default ON in this fork
        return bool(cfg.get("enabled", True))

    def _ftcache_maybe_init(self) -> None:
        if self._ftcache_client is not None:
            return
        if not self._ftcache_enabled():
            self._ftcache_client = False
            return
        try:
            trading_mode_val = (
                str(self.trading_mode.value)  # type: ignore[attr-defined]
                if getattr(self, "trading_mode", None) is not None
                else "spot"
            )
            self._ftcache_client = OhlcvCacheClient.get_or_spawn(
                exchange_id=self.id,  # type: ignore[attr-defined]
                trading_mode=trading_mode_val,
                bot_config=self._config,  # type: ignore[attr-defined]
            )
            logger.info(
                "cache client ready for %s/%s",
                self.id,  # type: ignore[attr-defined]
                trading_mode_val,
            )
        except Exception as e:
            if not self._ftcache_warned:
                logger.warning(
                    "could not initialise cache client (%s) — falling back to "
                    "direct ccxt for this bot", e,
                )
                self._ftcache_warned = True
            self._ftcache_client = False

    def _ftcache_warn_deprecated_config(self) -> None:
        """Inform the user that ccxt-level rate-limit knobs are now managed
        by the daemon."""
        if not self._ftcache_enabled():
            return
        exchange_conf = self._config.get("exchange") or {}  # type: ignore[attr-defined]
        ccxt_cfg = exchange_conf.get("ccxt_config") or {}
        if "rateLimit" in ccxt_cfg or ccxt_cfg.get("enableRateLimit") is True:
            logger.warning(
                "`exchange.ccxt_config.rateLimit` / `enableRateLimit` are "
                "ignored while the shared OHLCV cache is active. Rate "
                "limiting is centralised in the ftcache daemon across all "
                "bots. You can remove these keys, or opt out with "
                "`shared_ohlcv_cache.enabled: false`."
            )

    async def _async_get_candle_history(
        self,
        pair: str,
        timeframe: str,
        candle_type: CandleType,
        since_ms: int | None = None,
    ) -> "OHLCVResponse":
        self._ftcache_maybe_init()

        # Phase 0: only route live refresh (since_ms=None) through the cache.
        # Historic paths go direct to preserve existing behaviour.
        if since_ms is not None or not self._ftcache_client:
            return await super()._async_get_candle_history(  # type: ignore[misc]
                pair, timeframe, candle_type, since_ms,
            )

        client: OhlcvCacheClient = self._ftcache_client  # type: ignore[assignment]
        try:
            limit = self.ohlcv_candle_limit(  # type: ignore[attr-defined]
                timeframe, candle_type=candle_type, since_ms=since_ms,
            )
            return await client.fetch(
                pair=pair, timeframe=timeframe,
                candle_type=candle_type, since_ms=since_ms, limit=limit,
            )
        except CacheUnavailable as e:
            logger.warning(
                "cache fetch failed for %s %s (%s) — falling back to ccxt",
                pair, timeframe, e,
            )
            return await super()._async_get_candle_history(  # type: ignore[misc]
                pair, timeframe, candle_type, since_ms,
            )
