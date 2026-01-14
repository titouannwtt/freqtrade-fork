import logging
from typing import Any

from freqtrade.constants import Config
from freqtrade.enums import RunMode
from freqtrade.exceptions import OperationalException
from freqtrade.exchange import available_exchanges, is_exchange_known_ccxt, validate_exchange
from freqtrade.exchange.common import MAP_EXCHANGE_CHILDCLASS, SUPPORTED_EXCHANGES
from freqtrade.resolvers.exchange_resolver import ExchangeResolver


logger = logging.getLogger(__name__)


def _get_ft_has_overrides(exchange_name: str) -> dict[str, Any] | None:
    subclassed = {e["name"].lower(): e for e in ExchangeResolver.search_all_objects({}, False)}
    mapped = MAP_EXCHANGE_CHILDCLASS.get(exchange_name.lower(), exchange_name.lower()).lower()
    resolved = subclassed.get(mapped)
    if not resolved:
        return None

    get_ft_has = getattr(resolved["class"], "get_ft_has", None)
    if callable(get_ft_has):
        return get_ft_has() or None
    return None


def check_exchange(config: Config, check_for_bad: bool = True) -> bool:
    """
    Check if the exchange name in the config file is supported by Freqtrade
    :param check_for_bad: if True, check the exchange against the list of known 'bad'
                          exchanges
    :return: False if exchange is 'bad', i.e. is known to work with the bot with
             critical issues or does not work at all, crashes, etc. True otherwise.
             raises an exception if the exchange if not supported by ccxt
             and thus is not known for the Freqtrade at all.
    """

    if config["runmode"] in [
        RunMode.PLOT,
        RunMode.UTIL_NO_EXCHANGE,
        RunMode.OTHER,
    ] and not config.get("exchange", {}).get("name"):
        # Skip checking exchange in plot mode, since it requires no exchange
        return True
    logger.info("Checking exchange...")

    exchange = config.get("exchange", {}).get("name", "").lower()
    if not exchange:
        raise OperationalException(
            f"This command requires a configured exchange. You should either use "
            f"`--exchange <exchange_name>` or specify a configuration file via `--config`.\n"
            f"The following exchanges are available for Freqtrade: "
            f"{', '.join(available_exchanges())}"
        )

    if not is_exchange_known_ccxt(exchange):
        raise OperationalException(
            f'Exchange "{exchange}" is not known to the ccxt library '
            f"and therefore not available for the bot.\n"
            f"The following exchanges are available for Freqtrade: "
            f"{', '.join(available_exchanges())}"
        )

    ft_has_overrides = _get_ft_has_overrides(exchange)
    valid, reason, _, _ = validate_exchange(exchange, ft_has_overrides)
    if not valid:
        if check_for_bad:
            raise OperationalException(
                f'Exchange "{exchange}"  will not work with Freqtrade. Reason: {reason}.'
            )
        else:
            logger.warning(
                f'Exchange "{exchange}"  will not work with Freqtrade. Reason: {reason}.'
            )

    if MAP_EXCHANGE_CHILDCLASS.get(exchange, exchange) in SUPPORTED_EXCHANGES:
        logger.info(
            f'Exchange "{exchange}" is officially supported by the Freqtrade development team.'
        )
    else:
        logger.warning(
            f'Exchange "{exchange}" is known to the ccxt library, '
            f"available for the bot, but not officially supported "
            f"by the Freqtrade development team. "
            f"It may work flawlessly (please report back) or have serious issues. "
            f"Use it at your own discretion."
        )

    return True
