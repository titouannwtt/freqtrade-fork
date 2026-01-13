"""Tests for Kraken Futures exchange class"""

from __future__ import annotations

from copy import deepcopy

from ccxt.base.errors import NotSupported

from freqtrade.enums import CandleType, MarginMode, TradingMode
from freqtrade.exchange.exchange import Exchange
from freqtrade.exchange.krakenfutures import KrakenFutures
from tests.conftest import get_patched_exchange


def test_krakenfutures_get_ft_has():
    """Test that get_ft_has returns correct capability flags."""
    ft_has = KrakenFutures.get_ft_has()
    assert ft_has["fetchOrder"] is True
    assert ft_has["createMarketOrder"] is True
    assert ft_has["stoploss_on_exchange"] is True
    assert ft_has["stoploss_order_types"] == {"limit": "limit", "market": "market"}


def test_krakenfutures_ohlcv_candle_limit_caps_at_2000(mocker, default_conf):
    """Test that OHLCV candle limit is capped at 2000."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    assert isinstance(ex, KrakenFutures)

    mocker.patch.object(ex, "features", return_value=5000)

    assert ex.ohlcv_candle_limit("1m", candle_type=CandleType.FUTURES) == 2000


def test_krakenfutures_fetch_order_falls_back_to_open_orders(mocker, default_conf):
    """Test fetch_order falls back to open orders when fetchOrder not supported."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=NotSupported("fetchOrder not supported"),
        create=True,
    )
    mocker.patch.object(
        ex._api,
        "fetch_open_orders",
        return_value=[{"id": "abc", "status": "open"}],
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_closed_orders", return_value=[], create=True)

    res = ex.fetch_order("abc", "BTC/USD:USD")
    assert res["id"] == "abc"
    assert res["status"] == "open"


def test_krakenfutures_fetch_order_falls_back_when_super_raises_attributeerror(
    mocker, default_conf
):
    """Test fetch_order handles AttributeError from missing fetch_open_order."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=AttributeError("fetch_open_order missing"),
        create=True,
    )
    mocker.patch.object(
        ex._api,
        "fetch_open_orders",
        return_value=[{"id": "abc", "status": "open"}],
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_closed_orders", return_value=[], create=True)

    res = ex.fetch_order("abc", "BTC/USD:USD")
    assert res["id"] == "abc"
    assert res["status"] == "open"


def test_krakenfutures_fetch_order_falls_back_to_closed_orders(mocker, default_conf):
    """Test fetch_order falls back to closed orders when not found in open."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=NotSupported("fetchOrder not supported"),
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_open_orders", return_value=[], create=True)
    mocker.patch.object(
        ex._api,
        "fetch_closed_orders",
        return_value=[{"id": "def", "status": "closed"}],
        create=True,
    )

    res = ex.fetch_order("def", "BTC/USD:USD")
    assert res["id"] == "def"
    assert res["status"] == "closed"


def test_krakenfutures_fetch_order_returns_pseudo_order_when_not_found(mocker, default_conf):
    """When order is not found anywhere, KrakenFutures returns a pseudo order to avoid crashes."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=NotSupported("fetchOrder not supported"),
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_open_orders", return_value=[], create=True)
    mocker.patch.object(ex._api, "fetch_closed_orders", return_value=[], create=True)
    mocker.patch.object(ex._api, "historyGetOrders", return_value={"elements": []}, create=True)
    mocker.patch.object(ex._api, "historyGetTriggers", return_value={"elements": []}, create=True)

    res = ex.fetch_order("nope", "BTC/USD:USD")
    # Returns a pseudo order with status open and the requested id
    assert res["id"] == "nope"
    assert res["status"] == "open"
    assert res["symbol"] == "BTC/USD:USD"


def test_krakenfutures_fetch_order_falls_back_to_history_orders(mocker, default_conf):
    """Test fetch_order falls back to historyGetOrders endpoint."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=NotSupported("fetchOrder not supported"),
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_open_orders", return_value=[], create=True)
    mocker.patch.object(ex._api, "fetch_closed_orders", return_value=[], create=True)

    mocker.patch.object(
        ex._api,
        "historyGetOrders",
        return_value={
            "elements": [
                {
                    "event": {
                        "OrderCancelled": {
                            "order": {
                                "uid": "abc",
                                "direction": "Buy",
                                "quantity": "0.0002",
                                "filled": "0",
                                "timestamp": 1767962185989,
                                "limitPrice": "90338",
                            }
                        }
                    }
                }
            ]
        },
        create=True,
    )

    res = ex.fetch_order("abc", "BTC/USD:USD")
    assert res["id"] == "abc"
    assert res["status"] == "canceled"
    assert res["side"] == "buy"
    assert res["type"] == "limit"
    assert res["amount"] == 0.0002
    assert res["filled"] == 0.0


def test_krakenfutures_get_stop_params_adds_triggerprice_signal_and_reduceonly(
    mocker, default_conf
):
    """Test _get_stop_params adds triggerPrice, triggerSignal, and reduceOnly."""
    conf = deepcopy(default_conf)
    conf["trading_mode"] = TradingMode.FUTURES
    conf["margin_mode"] = MarginMode.ISOLATED

    if isinstance(conf.get("exchange"), dict):
        conf["exchange"]["triggerSignal"] = "mark"

    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    params = ex._get_stop_params(side="sell", ordertype="market", stop_price=90000.0)

    assert params["triggerPrice"] == 90000.0
    assert params["triggerSignal"] == "mark"
    assert params["reduceOnly"] is True


def test_krakenfutures_fetch_order_falls_back_to_history_triggers(mocker, default_conf):
    """Test fetch_order falls back to historyGetTriggers for stop orders."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=NotSupported("fetchOrder not supported"),
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_open_orders", return_value=[], create=True)
    mocker.patch.object(ex._api, "fetch_closed_orders", return_value=[], create=True)

    mocker.patch.object(ex._api, "historyGetOrders", return_value={"elements": []}, create=True)
    mocker.patch.object(
        ex._api,
        "historyGetTriggers",
        return_value={
            "elements": [
                {
                    "event": {
                        "TriggerCancelled": {
                            "trigger": {
                                "uid": "abc",
                                "direction": "Buy",
                                "quantity": "0.0002",
                                "timestamp": 1767962185989,
                                "triggerPrice": "136238",
                                "orderType": "stp",
                                "reduceOnly": False,
                            }
                        }
                    }
                }
            ]
        },
        create=True,
    )

    res = ex.fetch_order("abc", "BTC/USD:USD")
    assert res["id"] == "abc"
    assert res["status"] == "canceled"
    assert res["side"] == "buy"
    assert res["type"] == "market"
    assert res["stopPrice"] == 136238.0


def test_krakenfutures_fetch_order_normalizes_stopprice_and_type_from_trigger_info(
    mocker, default_conf
):
    """Test fetch_order normalizes stopPrice from trigger info and fixes order type."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(
        ex._api,
        "fetch_order",
        side_effect=NotSupported("fetchOrder not supported"),
        create=True,
    )
    mocker.patch.object(ex._api, "fetch_open_orders", return_value=[], create=True)
    mocker.patch.object(ex._api, "fetch_closed_orders", return_value=[], create=True)

    mocker.patch.object(ex._api, "historyGetOrders", return_value={"elements": []}, create=True)

    # stopPrice exists in the payload, but NOT inside the trigger dict that becomes "orderish"
    # This forces stopPrice to be picked up via _normalize_fetched_order scanning order["info"].
    mocker.patch.object(
        ex._api,
        "historyGetTriggers",
        return_value={
            "elements": [
                {
                    "event": {
                        "TriggerCancelled": {
                            "trigger": {
                                "uid": "abc",
                                "direction": "Buy",
                                "quantity": "0.0002",
                                "orderType": "lmt",
                            },
                            "stopPrice": "136983.0",
                        }
                    }
                }
            ]
        },
        create=True,
    )

    res = ex.fetch_order("abc", "BTC/USD:USD")
    assert res["id"] == "abc"
    assert res["status"] == "canceled"
    assert res["side"] == "buy"
    assert res["stopPrice"] == 136983.0
    assert res["type"] == "market"


def test_krakenfutures_exchange_has_create_market_order_override(mocker, default_conf):
    """Test exchange_has override returns True for createMarketOrder."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    ex._api.has = {"createMarketOrder": False}
    assert ex.exchange_has("createMarketOrder") is True


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
