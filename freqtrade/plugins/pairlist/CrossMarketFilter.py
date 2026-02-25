"""
Price pair list filter
"""

import logging

import ccxt.pro as ccxt_pro

from freqtrade.exceptions import OperationalException
from freqtrade.exchange.exchange_types import Tickers
from freqtrade.plugins.pairlist.IPairList import IPairList, PairlistParameter, SupportsBacktesting


logger = logging.getLogger(__name__)


class CrossMarketFilter(IPairList):
    supports_backtesting = SupportsBacktesting.BIASED

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._mode: str = self._pairlistconfig.get("mode", "whitelist")
        self._trading_mode: str = self._config["trading_mode"]
        self._stake_currency: str = self._config["stake_currency"]
        self._target_mode = "futures" if self._trading_mode == "spot" else "spot"

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
        mode = self._mode
        target_mode = self._target_mode
        msg = f"{self.name} - {mode.capitalize()} pairs that exists on {target_mode} market."
        return msg

    @staticmethod
    def description() -> str:
        return "Filter pairs if they exist on another market."

    @staticmethod
    def available_parameters() -> dict[str, PairlistParameter]:
        return {
            "mode": {
                "type": "option",
                "default": "whitelist",
                "options": ["whitelist", "blacklist"],
                "description": "Mode of operation",
                "help": "Mode of operation (whitelist/blacklist)",
            },
        }

    def get_base_list(self):
        target_mode = self._target_mode
        spot_only = True if target_mode == "spot" else False
        futures_only = True if target_mode == "futures" else False
        bases = [
            v.get("base", "")
            for k, v in self._exchange.get_markets(
                quote_currencies=[self._stake_currency],
                tradable_only=False,
                active_only=True,
                spot_only=spot_only,
                futures_only=futures_only,
            ).items()
        ]
        return bases

    prefixes = ("1000", "1000000", "1M", "K", "M")

    def filter_pairlist(self, pairlist: list[str], tickers: Tickers) -> list[str]:
        bases = self.get_base_list()
        is_whitelist_mode = self._mode == "whitelist"
        whitelisted_pairlist: list[str] = []
        filtered_pairlist = pairlist.copy()

        for pair in pairlist:
            base = self._exchange.get_pair_base_currency(pair)
            found_in_bases = base in bases
            if not found_in_bases:
                for prefix in self.prefixes:
                    test_prefix = f"{prefix}{base}"
                    if test_prefix in bases:
                        found_in_bases = True
                        break
            if found_in_bases:
                whitelisted_pairlist.append(pair)
                filtered_pairlist.remove(pair)

        return whitelisted_pairlist if is_whitelist_mode else filtered_pairlist
