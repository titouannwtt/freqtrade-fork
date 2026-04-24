"""
Hyperliquid subclass that routes OHLCV fetches through the shared cache
daemon. See freqtrade/ohlcv_cache/ for the full architecture.
"""

import logging

from freqtrade.exchange.hyperliquid import Hyperliquid
from freqtrade.ohlcv_cache.mixin import CachedExchangeMixin


logger = logging.getLogger(__name__)


class CachedHyperliquid(CachedExchangeMixin, Hyperliquid):
    """Hyperliquid with shared OHLCV cache.

    MRO: CachedHyperliquid -> CachedExchangeMixin -> Hyperliquid -> Exchange
    so that `super()._async_get_candle_history` in the mixin resolves to
    Hyperliquid (no override there) -> Exchange's implementation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ftcache_warn_deprecated_config()
