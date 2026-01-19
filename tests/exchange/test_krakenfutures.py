"""Tests for Kraken Futures exchange class"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock

from freqtrade.enums import CandleType, MarginMode, TradingMode
from freqtrade.exceptions import RetryableOrderError, TemporaryError
from freqtrade.exchange.exchange import Exchange
from freqtrade.exchange.krakenfutures import Krakenfutures
from tests.conftest import EXMS, get_patched_exchange


def test_krakenfutures_ft_has_overrides():
    """Test that _ft_has contains Kraken Futures stoploss settings."""
    ft_has = Krakenfutures._ft_has
    assert ft_has["stoploss_on_exchange"] is True
    assert ft_has["stoploss_order_types"] == {"limit": "limit", "market": "market"}
    assert ft_has["stop_price_param"] == "triggerPrice"
    assert ft_has["stop_price_type_field"] == "triggerSignal"


def test_krakenfutures_ohlcv_candle_limit_uses_ccxt_limit(mocker, default_conf):
    """Test that OHLCV candle limit follows CCXT feature limit."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    assert isinstance(ex, Krakenfutures)

    mocker.patch.object(ex, "features", return_value=2000)

    assert ex.ohlcv_candle_limit("1m", candle_type=CandleType.FUTURES) == 2000


def test_krakenfutures_fetch_order_falls_back_to_closed_orders(mocker, default_conf):
    """Fallback to fetch_closed_orders when fetch_order can't find the order."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(Exchange, "fetch_order", side_effect=RetryableOrderError("not found"))
    mocker.patch.object(
        ex,
        "exchange_has",
        side_effect=lambda endpoint: endpoint == "fetchClosedOrders",
    )
    mocker.patch.object(
        ex._api,
        "fetch_closed_orders",
        return_value=[{"id": "abc", "symbol": "BTC/USD:USD", "status": "closed"}],
        create=True,
    )

    res = ex.fetch_order("abc", "BTC/USD:USD")
    assert res["id"] == "abc"


def test_krakenfutures_fetch_order_falls_back_to_canceled_orders(mocker, default_conf):
    """Fallback to fetch_canceled_orders when closed orders don't contain the order."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        Exchange, "fetch_order", side_effect=TemporaryError("UUID string too large")
    )
    mocker.patch.object(
        ex,
        "exchange_has",
        side_effect=lambda endpoint: endpoint == "fetchCanceledOrders",
    )
    mocker.patch.object(
        ex._api,
        "fetch_canceled_orders",
        return_value=[{"id": "def", "symbol": "BTC/USD:USD", "status": "canceled"}],
        create=True,
    )

    res = ex.fetch_order("def", "BTC/USD:USD")
    assert res["id"] == "def"


def test_krakenfutures_create_stoploss_uses_trigger_price_type(mocker, default_conf):
    """Test create_stoploss uses triggerPrice, triggerSignal, and reduceOnly."""
    api_mock = MagicMock()
    api_mock.create_order = MagicMock(return_value={"id": "order-id", "info": {"foo": "bar"}})

    conf = deepcopy(default_conf)
    conf["dry_run"] = False
    conf["trading_mode"] = TradingMode.FUTURES
    conf["margin_mode"] = MarginMode.ISOLATED

    mocker.patch(f"{EXMS}.amount_to_precision", lambda s, x, y: y)
    mocker.patch(f"{EXMS}.price_to_precision", lambda s, x, y, **kwargs: y)

    ex = get_patched_exchange(mocker, conf, api_mock, exchange="krakenfutures")

    ex.create_stoploss(
        pair="ETH/BTC",
        amount=1,
        stop_price=90000.0,
        side="sell",
        order_types={"stoploss": "market", "stoploss_price_type": "mark"},
        leverage=1.0,
    )

    call_args = api_mock.create_order.call_args
    params = call_args[1].get("params") if call_args[1] else call_args[0][5]

    assert params["triggerPrice"] == 90000.0
    assert params["triggerSignal"] == "mark"
    assert params["reduceOnly"] is True


def test_krakenfutures_validate_stakecurrency_allows_eur(mocker, default_conf):
    """Test validate_stakecurrency allows EUR for multi-collateral accounts."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    ex.validate_stakecurrency("EUR")


def test_krakenfutures_get_balances_synth_usd_from_flex(mocker, default_conf):
    """Test get_balances synthesizes USD balance from flex account."""
    conf = dict(default_conf)
    conf["stake_currency"] = "USD"
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    sample = {
        "EUR": {"free": 10.0, "used": 0.0, "total": 10.0},
        "free": {"EUR": 10.0},
        "used": {"EUR": 0.0},
        "total": {"EUR": 10.0},
        "info": {
            "accounts": {
                "flex": {
                    "availableMargin": 11.0,
                    "balanceValue": 12.0,
                }
            }
        },
    }

    mocker.patch.object(Exchange, "get_balances", return_value=sample)
    res = ex.get_balances()
    assert res["USD"]["free"] == 11.0
    assert res["USD"]["total"] == 12.0


def test_krakenfutures_get_balances_falls_back_to_ccxt_fetch_balance(mocker, default_conf):
    """Test get_balances falls back to fetch_balance when no flex in initial response."""
    conf = dict(default_conf)
    conf["stake_currency"] = "USD"
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    # Base get_balances returns no info -> forces fallback
    mocker.patch.object(
        Exchange, "get_balances", return_value={"free": {}, "used": {}, "total": {}}
    )

    mocker.patch.object(
        ex._api,
        "fetch_balance",
        return_value={
            "free": {"EUR": 10.0},
            "used": {"EUR": 0.0},
            "total": {"EUR": 10.0},
            "info": {"accounts": {"flex": {"availableMargin": 11.0, "balanceValue": 12.0}}},
        },
        create=True,
    )

    res = ex.get_balances()
    assert res["free"]["USD"] == 11.0
    assert res["total"]["USD"] == 12.0
