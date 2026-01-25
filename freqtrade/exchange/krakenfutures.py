"""Kraken Futures exchange subclass"""

from __future__ import annotations

import logging
from typing import Any

from freqtrade.enums import MarginMode, PriceType, TradingMode
from freqtrade.exceptions import ExchangeError, RetryableOrderError, TemporaryError
from freqtrade.exchange.exchange import Exchange
from freqtrade.exchange.exchange_types import FtHas


logger = logging.getLogger(__name__)


class Krakenfutures(Exchange):
    """Kraken Futures exchange class.

    Contains adjustments needed for Freqtrade to work with this exchange.

    Key differences from spot Kraken:
    - Stop orders use triggerPrice/triggerSignal instead of stopPrice
    - Multi-collateral accounts require synthetic USD balance from flex account
    """

    _supported_trading_mode_margin_pairs: list[tuple[TradingMode, MarginMode]] = [
        (TradingMode.FUTURES, MarginMode.ISOLATED),
    ]

    # Freqtrade uses _ft_has (exchange_has_overrides) for config validation.
    _ft_has: FtHas = {
        "stoploss_on_exchange": True,
        "stoploss_order_types": {
            "limit": "limit",
            "market": "market",
        },
        # request param used by Exchange._get_stop_params
        "stop_price_param": "triggerPrice",
        # response key used by stoploss_adjust and general stop parsing
        "stop_price_prop": "stopPrice",
        # optional futures price type mapping (only used if stoploss_price_type is configured)
        "stop_price_type_field": "triggerSignal",
        "stop_price_type_value_mapping": {
            PriceType.LAST: "last",
            PriceType.MARK: "mark",
            PriceType.INDEX: "index",
        },
    }

    def get_balances(self, params: dict | None = None) -> dict[str, Any]:
        """
        Fetch account balances with special handling for Kraken Futures flex accounts.
        Kraken Futures supports "flex" (multi-collateral) accounts where users can hold
        multiple currencies as margin. CCXT returns these balances per-currency (EUR, etc.)
        but does not synthesize a USD balance, which Freqtrade expects as stake_currency.
        The flex account fields used:
        - availableMargin: USD value available for new positions (-> free)
        - balanceValue/portfolioValue: total USD value of account (-> total)
        - currencies[*].value: fallback sum if above fields missing
        """
        balances = super().get_balances(params=params)

        stake = str(self._config.get("stake_currency", "")).upper()
        if stake != "USD":
            return balances

        flex = self._get_flex_account(balances, params)
        if flex is None:
            return balances

        usd_free, usd_total = self._extract_usd_from_flex(flex)
        if usd_free is None or usd_total is None:
            return balances

        # Preserve existing USD if higher (usually dust)
        if isinstance(balances.get("free"), dict):
            existing = self._safe_float(balances["free"].get("USD"))
            if existing is not None:
                usd_free = max(existing, usd_free)

        self._apply_usd_balances(balances, usd_free, usd_total)
        return balances

    def _get_flex_account(
        self, balances: dict[str, Any], params: dict | None
    ) -> dict[str, Any] | None:
        """Try to get flex account data from cached balances or fetch fresh."""
        flex = self._extract_flex_from_raw(balances)
        if flex is not None:
            return flex

        try:
            raw = self._api.fetch_balance(params or {})
        except Exception:
            return None
        return self._extract_flex_from_raw(raw)

    @staticmethod
    def _extract_flex_from_raw(raw: dict[str, Any] | None) -> dict[str, Any] | None:
        """Navigate raw -> info -> accounts -> flex (Kraken Futures multi-collateral account)."""
        if not isinstance(raw, dict):
            return None
        info = raw.get("info")
        if not isinstance(info, dict):
            return None
        accounts = info.get("accounts")
        if not isinstance(accounts, dict):
            return None
        flex = accounts.get("flex")
        return flex if isinstance(flex, dict) else None

    def _extract_usd_from_flex(self, flex: dict[str, Any]) -> tuple[float | None, float | None]:
        usd_free = self._safe_float(flex.get("availableMargin") or flex.get("available_margin"))
        usd_total = self._safe_float(
            flex.get("balanceValue") or flex.get("collateralValue") or flex.get("portfolioValue")
        )

        # Fallback: sum currencies[*].value
        if usd_total is None:
            usd_total = self._sum_currencies_value(flex.get("currencies"))

        # Fill missing with the other if available
        if usd_total is None and usd_free is not None:
            usd_total = usd_free
        if usd_free is None and usd_total is not None:
            usd_free = usd_total

        return usd_free, usd_total

    def _sum_currencies_value(self, currencies: Any) -> float | None:
        """Sum value fields from currencies dict."""
        if not isinstance(currencies, dict):
            return None
        total = 0.0
        found = False
        for cur in currencies.values():
            if isinstance(cur, dict):
                v = self._safe_float(cur.get("value"))
                if v is not None:
                    total += v
                    found = True
        return total if found else None

    @staticmethod
    def _apply_usd_balances(balances: dict[str, Any], usd_free: float, usd_total: float) -> None:
        """Update balances dict with USD values."""
        balances["USD"] = {"free": usd_free, "used": 0.0, "total": usd_total}
        balances.setdefault("free", {})
        balances.setdefault("used", {})
        balances.setdefault("total", {})

        if isinstance(balances["free"], dict):
            balances["free"]["USD"] = usd_free
        if isinstance(balances["used"], dict):
            balances["used"]["USD"] = 0.0
        if isinstance(balances["total"], dict):
            balances["total"]["USD"] = usd_total

    def validate_stakecurrency(self, stake_currency: str) -> None:
        # Kraken Futures multi-collateral allows EUR collateral even if markets look USD-settled.
        if str(stake_currency).upper() == "EUR":
            return
        super().validate_stakecurrency(stake_currency)

    def fetch_order(
        self, order_id: str, pair: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Kraken Futures fetchOrder is backed by /orders/status which only returns
        open orders or orders closed within the last 5 seconds.
        Fall back to closed/canceled order endpoints for older orders.
        """
        params = params or {}
        try:
            return super().fetch_order(order_id, pair, params=params)
        except (RetryableOrderError, TemporaryError) as err:
            order = self._fetch_order_from_closed_or_canceled(order_id, pair, params)
            if order is not None:
                return order
            raise err

    def _fetch_order_from_closed_or_canceled(
        self, order_id: str, pair: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        if self.exchange_has("fetchClosedOrders"):
            orders = self._api.fetch_closed_orders(pair, params=params)
            for order in orders or []:
                if str(order.get("id")) == str(order_id):
                    return self._order_contracts_to_amount(order)

        if self.exchange_has("fetchCanceledOrders"):
            orders = self._api.fetch_canceled_orders(pair, params=params)
            for order in orders or []:
                if str(order.get("id")) == str(order_id):
                    return self._order_contracts_to_amount(order)

        return None

    def get_funding_fees(self, pair: str, amount: float, is_short: bool, open_date) -> float:
        """CCXT currently does not support Kraken Futures fetchFundingHistory."""
        if self.trading_mode == TradingMode.FUTURES:
            try:
                return self._fetch_and_calculate_funding_fees(pair, amount, is_short, open_date)
            except ExchangeError:
                logger.warning(f"Could not update funding fees for {pair}.")
        return 0.0

    @staticmethod
    def _safe_float(v: Any) -> float | None:
        try:
            if v is None or v == "":
                return None
            return float(v)
        except (TypeError, ValueError):
            return None
