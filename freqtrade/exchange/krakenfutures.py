"""Kraken Futures exchange subclass"""

import logging
from typing import Any

import ccxt

from freqtrade.enums import MarginMode, PriceType, TradingMode
from freqtrade.exceptions import (
    DDosProtection,
    ExchangeError,
    InvalidOrderException,
    OperationalException,
    RetryableOrderError,
    TemporaryError,
)
from freqtrade.exchange.common import API_FETCH_ORDER_RETRY_COUNT, retrier
from freqtrade.exchange.exchange import Exchange
from freqtrade.exchange.exchange_types import CcxtBalances, CcxtOrder, FtHas


logger = logging.getLogger(__name__)


class Krakenfutures(Exchange):
    """Kraken Futures exchange class.

    Contains adjustments needed for Freqtrade to work with this exchange.

    Key differences from spot Kraken:
    - Stop orders use triggerPrice/triggerSignal instead of stopPrice
    - Flex (multi-collateral) accounts need USD balance synthesis
    """

    _supported_trading_mode_margin_pairs: list[tuple[TradingMode, MarginMode]] = [
        (TradingMode.FUTURES, MarginMode.ISOLATED),
    ]

    _ft_has: FtHas = {
        "stoploss_on_exchange": True,
        "stoploss_order_types": {
            "limit": "limit",
            "market": "market",
        },
        "stop_price_param": "triggerPrice",
        "stop_price_prop": "stopPrice",
        "stop_price_type_field": "triggerSignal",
        "stop_price_type_value_mapping": {
            PriceType.LAST: "last",
            PriceType.MARK: "mark",
            PriceType.INDEX: "index",
        },
    }

    @retrier
    def get_balances(self, params: dict | None = None) -> CcxtBalances:
        """
        Fetch balances with USD synthesis for flex (multi-collateral) accounts.

        Kraken Futures flex accounts hold multiple currencies as collateral.
        CCXT returns per-currency balances but doesn't expose margin values
        as a USD balance. This override synthesizes a USD entry from flex account data
        when stake_currency is USD.

        Field mapping (margin-centric for internal consistency):
        - free: availableMargin (margin available for new positions)
        - total: marginEquity (haircut-adjusted collateral + unrealized P&L)
        - used: total - free (margin currently in use)

        Fallback chain for total: marginEquity -> portfolioValue -> balanceValue
        """
        try:
            balances = self._api.fetch_balance(params or {})

            # Only synthesize USD if stake_currency is USD
            stake = str(self._config.get("stake_currency", "")).upper()
            if stake != "USD":
                # Skip USD synthesis for non-USD stake currencies
                balances.pop("info", None)
                balances.pop("free", None)
                balances.pop("total", None)
                balances.pop("used", None)
                self._log_exchange_response("fetch_balance", balances, add_info=params)
                return balances

            # For flex accounts, synthesize USD balance from margin values
            info = balances.get("info", {})
            accounts = info.get("accounts", {}) if isinstance(info, dict) else {}
            flex = accounts.get("flex", {}) if isinstance(accounts, dict) else {}

            if flex:
                usd_free = self._safe_float(flex.get("availableMargin"))
                # Prefer marginEquity for consistency (same basis as availableMargin)
                raw_total = (
                    flex.get("marginEquity")
                    or flex.get("portfolioValue")
                    or flex.get("balanceValue")
                )
                usd_total = self._safe_float(raw_total)
                if usd_free is not None or usd_total is not None:
                    # Use available value for both if only one is present
                    usd_free = usd_free if usd_free is not None else usd_total
                    usd_total = usd_total if usd_total is not None else usd_free
                    # Both values are guaranteed to be present after fallback.
                    usd_used = max(0.0, usd_total - usd_free)
                    balances["USD"] = {"free": usd_free, "used": usd_used, "total": usd_total}

            # Remove additional info from ccxt results (same as base class)
            balances.pop("info", None)
            balances.pop("free", None)
            balances.pop("total", None)
            balances.pop("used", None)

            self._log_exchange_response("fetch_balance", balances, add_info=params)
            return balances
        except ccxt.DDoSProtection as e:
            raise DDosProtection(e) from e
        except (ccxt.OperationFailed, ccxt.ExchangeError) as e:
            raise TemporaryError(
                f"Could not get balance due to {e.__class__.__name__}. Message: {e}"
            ) from e
        except ccxt.BaseError as e:
            raise OperationalException(e) from e

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """Convert value to float, returning None if conversion fails."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @retrier(retries=API_FETCH_ORDER_RETRY_COUNT)
    def fetch_order(
        self, order_id: str, pair: str, params: dict[str, Any] | None = None
    ) -> CcxtOrder:
        """Fetch order with direct CCXT call and fallback to history endpoints."""
        if self._config.get("dry_run"):
            return self.fetch_dry_run_order(order_id)

        params = params or {}
        try:
            order = self._api.fetch_order(order_id, pair, params=params)
            self._log_exchange_response("fetch_order", order)
            return self._order_contracts_to_amount(order)
        except ccxt.OrderNotFound:
            # Expected for older Kraken Futures orders not visible in orders/status.
            pass
        except ccxt.DDoSProtection as e:
            raise DDosProtection(e) from e
        except ccxt.InvalidOrder as e:
            msg = f"Tried to get an invalid order (pair: {pair} id: {order_id}). Message: {e}"
            raise InvalidOrderException(msg) from e
        except (ccxt.OperationFailed, ccxt.ExchangeError):
            # Fallback to history endpoints for temporary/status endpoint gaps.
            pass
        except ccxt.BaseError as e:
            raise OperationalException(e) from e

        order = self._fetch_order_fallback(order_id, pair, params)
        if order is not None:
            return order

        raise RetryableOrderError(f"Order not found in any endpoint (pair: {pair} id: {order_id})")

    def _fetch_order_fallback(
        self, order_id: str, pair: str, params: dict[str, Any]
    ) -> CcxtOrder | None:
        """Search open, closed, and canceled order endpoints for order_id."""
        order_id_str = str(order_id)

        # Open orders: Kraken returns all symbols and includes triggers by default.
        order = self._find_order_in_list(self._api.fetch_open_orders, None, params, order_id_str)
        if order is not None:
            return order

        # Closed/canceled: use pair and optional trigger=True for stoplosses.
        for fetch_fn in (self._api.fetch_closed_orders, self._api.fetch_canceled_orders):
            order = self._find_order_in_list(fetch_fn, pair, params, order_id_str)
            if order is not None:
                return order
            # Trigger orders (stoplosses) only supported on history endpoints
            if not params.get("trigger"):
                order = self._find_order_in_list(
                    fetch_fn, pair, {**params, "trigger": True}, order_id_str
                )
                if order is not None:
                    return order

        return None

    def _find_order_in_list(
        self,
        fetch_fn,
        symbol: str | None,
        params: dict[str, Any],
        order_id_str: str,
    ) -> CcxtOrder | None:
        """Fetch orders and return matching order_id, or None."""
        try:
            for order in fetch_fn(symbol, params=params) or []:
                if str(order.get("id")) == order_id_str:
                    return self._order_contracts_to_amount(order)
        except (ccxt.OrderNotFound, ccxt.InvalidOrder) as e:
            logger.debug(f"{fetch_fn.__name__} failed: {e}")
            return None
        except ccxt.DDoSProtection as e:
            raise DDosProtection(e) from e
        except (ccxt.OperationFailed, ccxt.ExchangeError) as e:
            raise TemporaryError(
                f"Could not get order due to {e.__class__.__name__}. Message: {e}"
            ) from e
        except ccxt.BaseError as e:
            raise OperationalException(e) from e
        return None

    @staticmethod
    def _fix_trigger_order_id(order: dict) -> dict:
        """
        Fix CCXT trigger order response where top-level 'id' is None.

        Kraken Futures trigger orders return 'id': None in CCXT responses,
        but the actual order ID is in info.order.orderId. Extract and set it.
        """
        if order.get("id") is None:
            info = order.get("info", {})
            inner_order = info.get("order", {}) if isinstance(info, dict) else {}
            if isinstance(inner_order, dict) and inner_order.get("orderId"):
                order["id"] = inner_order["orderId"]
        return order

    def cancel_stoploss_order(self, order_id: str, pair: str, params: dict | None = None) -> dict:
        """Cancel stoploss order and fix CCXT response for trigger orders."""
        params = params or {}
        params["trigger"] = True
        order = self.cancel_order(order_id, pair, params)
        return self._fix_trigger_order_id(order)

    def fetch_stoploss_order(
        self, order_id: str, pair: str, params: dict | None = None
    ) -> CcxtOrder:
        """Fetch stoploss order and fix CCXT response for trigger orders."""
        params = params or {}
        params["trigger"] = True
        order = self.fetch_order(order_id, pair, params)
        return self._fix_trigger_order_id(order)

    def get_funding_fees(self, pair: str, amount: float, is_short: bool, open_date) -> float:
        """Fetch funding fees, returning 0.0 if retrieval fails."""
        if self.trading_mode == TradingMode.FUTURES:
            try:
                return self._fetch_and_calculate_funding_fees(pair, amount, is_short, open_date)
            except ExchangeError:
                logger.warning(f"Could not update funding fees for {pair}.")
        return 0.0
