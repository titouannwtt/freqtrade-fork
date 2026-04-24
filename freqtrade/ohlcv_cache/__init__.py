"""
Shared OHLCV cache daemon.

Phase 0 PoC: single-exchange (Hyperliquid), single-candle-type (FUTURES),
no partial-range merge. Validates the end-to-end architecture before
broadening scope in later phases.

See CLAUDE.md / design doc for full architecture.
"""

from freqtrade.ohlcv_cache.defaults import EXCHANGE_DEFAULTS


__all__ = ["EXCHANGE_DEFAULTS"]
