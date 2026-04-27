"""
This module loads custom exchanges
"""

import logging
from inspect import isclass
from typing import Any

import freqtrade.exchange as exchanges
from freqtrade.constants import Config, ExchangeConfig
from freqtrade.exchange import MAP_EXCHANGE_CHILDCLASS, Exchange
from freqtrade.resolvers.iresolver import IResolver


logger = logging.getLogger(__name__)


class ExchangeResolver(IResolver):
    """
    This class contains all the logic to load a custom exchange class
    """

    object_type = Exchange

    @staticmethod
    def load_exchange(
        config: Config,
        *,
        exchange_config: ExchangeConfig | None = None,
        validate: bool = True,
        load_leverage_tiers: bool = False,
    ) -> Exchange:
        """
        Load the custom class from config parameter
        :param exchange_name: name of the Exchange to load
        :param config: configuration dictionary
        """
        exchange_name: str = config["exchange"]["name"]
        # Map exchange name to avoid duplicate classes for identical exchanges
        exchange_name = MAP_EXCHANGE_CHILDCLASS.get(exchange_name, exchange_name)
        exchange_name = exchange_name.title()

        # Fork-specific: prefer the Cached* subclass when the shared OHLCV
        # cache is enabled (default on). If no Cached* variant exists for
        # this exchange yet, fall back to the regular subclass.
        candidate_names: list[str] = []
        cache_cfg = config.get("shared_ohlcv_cache") or {}
        if cache_cfg.get("enabled", True):
            candidate_names.append(f"Cached{exchange_name}")
        candidate_names.append(exchange_name)

        exchange = None
        last_error: Exception | None = None
        for candidate in candidate_names:
            try:
                exchange = ExchangeResolver._load_exchange(
                    candidate,
                    kwargs={
                        "config": config,
                        "validate": validate,
                        "exchange_config": exchange_config,
                        "load_leverage_tiers": load_leverage_tiers,
                    },
                )
                if exchange:
                    break
            except ImportError as e:
                last_error = e
                continue

        if not exchange:
            if last_error is not None:
                logger.info(
                    f"No specific subclass found (tried {candidate_names}). "
                    f"Using the generic class instead."
                )
            exchange = Exchange(
                config,
                validate=validate,
                exchange_config=exchange_config,
            )
        return exchange

    @staticmethod
    def _load_exchange(exchange_name: str, kwargs: dict) -> Exchange:
        """
        Loads the specified exchange.
        Only checks for exchanges exported in freqtrade.exchanges
        :param exchange_name: name of the module to import
        :return: Exchange instance or None
        """

        try:
            ex_class = getattr(exchanges, exchange_name)

            exchange = ex_class(**kwargs)
            if exchange:
                logger.info(f"Using resolved exchange '{exchange_name}'...")
                return exchange
        except AttributeError:
            # Pass and raise ImportError instead
            pass

        raise ImportError(
            f"Impossible to load Exchange '{exchange_name}'. This class does not exist "
            "or contains Python code errors."
        )

    @classmethod
    def search_all_objects(
        cls, config: Config, enum_failed: bool, recursive: bool = False
    ) -> list[dict[str, Any]]:
        """
        Searches for valid objects
        :param config: Config object
        :param enum_failed: If True, will return None for modules which fail.
            Otherwise, failing modules are skipped.
        :param recursive: Recursively walk directory tree searching for strategies
        :return: List of dicts containing 'name', 'class' and 'location' entries
        """
        result = []
        for exchange_name in dir(exchanges):
            exchange = getattr(exchanges, exchange_name)
            if isclass(exchange) and issubclass(exchange, Exchange):
                result.append(
                    {
                        "name": exchange_name,
                        "class": exchange,
                        "location": exchange.__module__,
                        "location_rel: ": exchange.__module__.replace("freqtrade.", ""),
                    }
                )
        return result
