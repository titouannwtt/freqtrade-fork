"""Kraken Futures exchange subclass"""

from __future__ import annotations

import logging
import time
from typing import Any

from freqtrade.enums import MarginMode, PriceType, TradingMode
from freqtrade.exceptions import ExchangeError, RetryableOrderError
from freqtrade.exchange.common import retrier
from freqtrade.exchange.exchange import Exchange
from freqtrade.exchange.exchange_types import FtHas


logger = logging.getLogger(__name__)


class Krakenfutures(Exchange):
    """Kraken Futures exchange class.

    Contains adjustments needed for Freqtrade to work with this exchange.

    Key differences from spot Kraken:
    - CCXT does not implement fetchOrder; we emulate via open/closed/history endpoints
    - Stop orders use triggerPrice/triggerSignal instead of stopPrice
    - Multi-collateral accounts require synthetic USD balance from flex account
    - OHLCV limit capped at 2000 candles
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
        "ohlcv_candle_limit": 2000,
        # override ccxt has-gaps
        "exchange_has_overrides": {
            "fetchOrder": True,
            "createMarketOrder": True,
        },
    }

    @classmethod
    def get_ft_has(cls) -> dict[str, Any]:
        return cls._ft_has.get("exchange_has_overrides", {})

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

    @retrier
    def fetch_order(
        self,
        order_id: str,
        pair: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = params or {}

        try:
            order = self.fetch_order_emulated(order_id, pair, params)
            return self._normalize_fetched_order(order)
        except RetryableOrderError:
            pass

        order = self._fetch_order_from_history(order_id, pair, params)
        if order is not None:
            return self._normalize_fetched_order(order)

        raise RetryableOrderError(f"Order {order_id} not found on exchange for pair {pair}.")

    def get_funding_fees(self, pair: str, amount: float, is_short: bool, open_date) -> float:
        """CCXT currently does not support Kraken Futures fetchFundingHistory."""
        if self.trading_mode == TradingMode.FUTURES:
            try:
                return self._fetch_and_calculate_funding_fees(pair, amount, is_short, open_date)
            except ExchangeError:
                logger.warning(f"Could not update funding fees for {pair}.")
        return 0.0

    def _strip_history_params(self, params: dict[str, Any]) -> dict[str, Any]:
        if not params:
            return {}
        # These time-range params are only valid for history endpoints.
        history_keys = {"since", "before", "from", "to"}
        return {k: v for k, v in params.items() if k not in history_keys}

    def fetch_order_emulated(
        self, order_id: str, pair: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        list_params = self._strip_history_params(params)

        try:
            open_orders = self.fetch_open_orders(pair, params=list_params)
        except Exception:
            open_orders = []

        for o in open_orders:
            if self._contains_value(o, order_id):
                return self._order_contracts_to_amount(o)

        try:
            closed_orders = self.fetch_closed_orders(pair, params=list_params)
        except Exception:
            closed_orders = []

        for o in closed_orders:
            if self._contains_value(o, order_id):
                return self._order_contracts_to_amount(o)

        raise RetryableOrderError(f"Order not found (pair: {pair} id: {order_id}).")

    def _fetch_order_from_history(
        self, order_id: str, pair: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        # Kraken Futures has separate history feeds for orders and triggers.
        for method_name in ("historyGetOrders", "historyGetTriggers"):
            order = self._fetch_order_from_history_method(method_name, order_id, pair, params)
            if order is not None:
                return order
        return None

    def _fetch_order_from_history_method(
        self,
        method_name: str,
        order_id: str,
        pair: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not hasattr(self._api, method_name):
            return None

        hist_params = dict(params)
        if not any(k in hist_params for k in ("since", "before", "from", "to")):
            now_ms = int(getattr(self._api, "milliseconds", lambda: int(time.time() * 1000))())
            hist_params["since"] = now_ms - 48 * 60 * 60 * 1000  # 48 hours lookback

        try:
            hist = getattr(self._api, method_name)(hist_params)
        except Exception:
            return None

        elements = self._extract_history_elements(hist)
        return self._parse_order_from_history_elements(elements, order_id, pair)

    @staticmethod
    def _extract_history_elements(hist: Any) -> list[dict[str, Any]]:
        if isinstance(hist, list):
            return [x for x in hist if isinstance(x, dict)]

        if not isinstance(hist, dict):
            return []

        if isinstance(hist.get("elements"), list):
            return [x for x in hist["elements"] if isinstance(x, dict)]

        result = hist.get("result")
        if isinstance(result, dict) and isinstance(result.get("elements"), list):
            return [x for x in result["elements"] if isinstance(x, dict)]

        events = hist.get("events")
        if isinstance(events, list):
            return [x for x in events if isinstance(x, dict)]

        return []

    def _parse_order_from_history_elements(
        self, elements: list[dict[str, Any]], order_id: str, pair: str
    ) -> dict[str, Any] | None:
        for el in elements:
            event = el.get("event") or el.get("events") or {}
            if not isinstance(event, dict):
                continue

            for event_name, payload in event.items():
                if not isinstance(payload, dict):
                    continue

                orderish = self._extract_orderish(payload)
                uid = self._extract_uid(orderish, payload)

                if uid is None and self._contains_value(payload, order_id):
                    uid = order_id

                if str(uid) != str(order_id):
                    continue

                return self._build_ccxt_like_order_from_history(
                    el, str(event_name), orderish, order_id, pair
                )

        return None

    @staticmethod
    def _extract_orderish(payload: dict[str, Any]) -> dict[str, Any]:
        for key in ("order", "trigger", "triggerOrder"):
            v = payload.get(key)
            if isinstance(v, dict):
                return v
        return payload

    @staticmethod
    def _extract_uid(orderish: dict[str, Any], payload: dict[str, Any]) -> Any:
        keys = (
            "uid",
            "id",
            "orderId",
            "order_id",
            "orderUid",
            "triggerId",
            "trigger_id",
            "triggerUid",
            "triggerOrderUid",
        )
        for k in keys:
            if k in orderish:
                return orderish.get(k)
        for k in keys:
            if k in payload:
                return payload.get(k)
        return None

    @staticmethod
    def _contains_value(obj: Any, needle: str) -> bool:
        if isinstance(obj, dict):
            return any(Krakenfutures._contains_value(v, needle) for v in obj.values())
        if isinstance(obj, list):
            return any(Krakenfutures._contains_value(v, needle) for v in obj)
        return str(obj) == str(needle)

    def _build_ccxt_like_order_from_history(
        self,
        el: dict[str, Any],
        event_name: str,
        order: dict[str, Any],
        order_id: str,
        pair: str,
    ) -> dict[str, Any]:
        status = self._map_history_event_to_status(event_name)

        amount = self._safe_float(order.get("quantity") or order.get("qty"))
        filled = self._safe_float(
            order.get("filled") or order.get("filledQty") or order.get("filled_qty")
        )
        price = self._safe_float(order.get("limitPrice") or order.get("price"))
        stop_price = self._safe_float(
            order.get("stopPrice")
            or order.get("triggerPrice")
            or order.get("trigger_price")
            or order.get("stop_price")
        )

        side_raw = str(order.get("direction") or order.get("side") or "").lower()
        if not side_raw and isinstance(order.get("buy"), bool):
            side_raw = "buy" if order["buy"] else "sell"
        side = "buy" if side_raw == "buy" else "sell" if side_raw == "sell" else None

        order_type = self._infer_order_type_from_history(order, price)

        remaining = None
        if amount is not None and filled is not None:
            remaining = max(amount - filled, 0.0)

        ts = order.get("timestamp") or order.get("time") or el.get("timestamp") or el.get("time")
        ts_int = int(ts) if ts is not None else None

        reduce_only = order.get("reduceOnly")
        if isinstance(reduce_only, str):
            reduce_only = reduce_only.lower() == "true"

        result: dict[str, Any] = {
            "id": order_id,
            "symbol": pair,
            "status": status,
            "side": side,
            "type": order_type,
            "price": price,
            "amount": amount,
            "filled": filled,
            "remaining": remaining,
            "timestamp": ts_int,
            "datetime": self._api.iso8601(ts_int) if ts_int is not None else None,
            "info": el,
        }

        if stop_price is not None:
            result["stopPrice"] = stop_price

        if isinstance(reduce_only, bool):
            result["reduceOnly"] = reduce_only

        return result

    @staticmethod
    def _infer_order_type_from_history(order: dict[str, Any], price: float | None) -> str | None:
        raw = str(order.get("orderType") or order.get("type") or "").lower()

        if raw in ("lmt", "limit", "post", "ioc"):
            return "limit"
        if raw in ("mkt", "market"):
            return "market"

        if raw in (
            "stp",
            "stop",
            "take_profit",
            "takeprofit",
            "take-profit",
            "trailing_stop",
            "trailingstop",
        ):
            return "limit" if price is not None else "market"

        if price is not None:
            return "limit"
        return None

    @staticmethod
    def _map_history_event_to_status(event_name: str) -> str:
        name = (event_name or "").lower()
        if "cancel" in name:
            return "canceled"
        if "reject" in name:
            return "rejected"
        if "place" in name:
            return "open"
        return "unknown"

    @staticmethod
    def _safe_float(v: Any) -> float | None:
        try:
            if v is None or v == "":
                return None
            return float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _find_first_value(obj: Any, keys: set[str]) -> Any | None:
        if obj is None:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in keys and v not in (None, ""):
                    return v
                found = Krakenfutures._find_first_value(v, keys)
                if found is not None:
                    return found
            return None
        if isinstance(obj, list):
            for v in obj:
                found = Krakenfutures._find_first_value(v, keys)
                if found is not None:
                    return found
            return None
        return None

    def _normalize_fetched_order(self, order: dict[str, Any]) -> dict[str, Any]:
        # 1) Ensure stopPrice exists for trigger orders
        if order.get("stopPrice") is None:
            raw = (
                order.get("triggerPrice")
                or order.get("trigger_price")
                or order.get("stop_price")
                or self._find_first_value(
                    order.get("info"),
                    {"stopPrice", "triggerPrice", "stop_price", "trigger_price"},
                )
            )
            sp = self._safe_float(raw)
            if sp is not None:
                order["stopPrice"] = sp

        # 2) Fix type when we clearly have a market trigger (no limit price, but has stopPrice)
        if (
            order.get("type") in (None, "limit")
            and order.get("price") is None
            and order.get("stopPrice") is not None
        ):
            order["type"] = "market"

        return order

    def fetch_open_orders(
        self,
        pair: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params = self._strip_history_params(params or {})
        return self._api.fetch_open_orders(pair, since, limit, params)

    def fetch_closed_orders(
        self,
        pair: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params = self._strip_history_params(params or {})
        return self._api.fetch_closed_orders(pair, since, limit, params)
