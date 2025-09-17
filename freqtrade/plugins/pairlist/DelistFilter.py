"""
Delist pair list filter
"""

import logging
from datetime import UTC, datetime, timedelta

from freqtrade.exceptions import OperationalException
from freqtrade.exchange.exchange_types import Ticker
from freqtrade.plugins.pairlist.IPairList import IPairList, PairlistParameter, SupportsBacktesting


logger = logging.getLogger(__name__)


class DelistFilter(IPairList):
    supports_backtesting = SupportsBacktesting.NO

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._max_days_from_now = self._pairlistconfig.get("max_days_from_now", 0)
        if self._max_days_from_now < 0:
            raise OperationalException("DelistFilter requires max_days_from_now to be >= 0")
        self._enabled = self._max_days_from_now >= 0

    @property
    def needstickers(self) -> bool:
        """
        Boolean property defining if tickers are necessary.
        If no Pairlist requires tickers, an empty Dict is passed
        as tickers argument to filter_pairlist
        """
        return False

    def short_desc(self) -> str:
        """
        Short whitelist method description - used for startup-messages
        """
        return (
            f"{self.name} - Filtering pairs that will be delisted"
            + (
                f" in the next {self._max_days_from_now} days"
                if self._max_days_from_now > 0
                else ""
            )
            + "."
        )

    @staticmethod
    def description() -> str:
        return "Filter pairs that will bbe delisted on exchange."

    @staticmethod
    def available_parameters() -> dict[str, PairlistParameter]:
        return {
            "max_days_from_now": {
                "type": "number",
                "default": 0,
                "description": "Max days from now",
                "help": (
                    "Remove pairs that will be delisted in the next X days. Set to 0 to remove all."
                ),
            },
        }

    def _validate_pair(self, pair: str, ticker: Ticker | None) -> bool:
        """
        Check if pair will be delisted.
        :param pair: Pair that's currently validated
        :param ticker: ticker dict as returned from ccxt.fetch_ticker
        :return: True if the pair can stay, false if it should be removed
        """
        delist_date = self._exchange.check_delisting_time(pair)

        if delist_date is not None:
            remove_pair = self._max_days_from_now == 0
            if self._max_days_from_now > 0:
                current_datetime = datetime.now(UTC)
                max_delist_date = current_datetime + timedelta(days=self._max_days_from_now)
                remove_pair = delist_date <= max_delist_date

            if remove_pair:
                self.log_once(
                    f"Removed {pair} from whitelist, because it will be delisted on {delist_date}.",
                    logger.info,
                )
                return False

        return True
