"""Tests for Kraken Futures exchange class"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from freqtrade.enums import CandleType, MarginMode, TradingMode
from freqtrade.exceptions import ExchangeError, RetryableOrderError, TemporaryError
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


def test_krakenfutures_get_leverage_tiers_fills_contracts(mocker, default_conf):
    """Fill missing min/maxNotional from contracts/maxPositionSize in leverage tiers."""
    mock_markets = {
        "BTC/USD:USD": {
            "info": {"maxPositionSize": 1000000},
            "contractSize": 1.0,
        }
    }
    ex = get_patched_exchange(
        mocker, default_conf, exchange="krakenfutures", mock_markets=mock_markets
    )
    assert isinstance(ex, Krakenfutures)

    sample_tiers = {
        "BTC/USD:USD": [
            {
                "minNotional": None,
                "maxNotional": None,
                "maintenanceMarginRate": 0.01,
                "maxLeverage": 50.0,
                "info": {"contracts": 0},
            },
            {
                "minNotional": None,
                "maxNotional": None,
                "maintenanceMarginRate": 0.02,
                "maxLeverage": 25.0,
                "info": {"contracts": 500000},
            },
        ]
    }

    mocker.patch.object(Exchange, "get_leverage_tiers", return_value=sample_tiers)
    tiers = ex.get_leverage_tiers()
    pair_tiers = tiers["BTC/USD:USD"]
    assert pair_tiers[0]["minNotional"] == 0.0
    assert pair_tiers[0]["maxNotional"] == 500000.0
    assert pair_tiers[1]["minNotional"] == 500000.0
    assert pair_tiers[1]["maxNotional"] == 1000000.0


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


def test_krakenfutures_fetch_order_reraises_when_no_fallback(mocker, default_conf):
    """Re-raise when fallback cannot locate the order."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(Exchange, "fetch_order", side_effect=RetryableOrderError("not found"))
    mocker.patch.object(ex, "_fetch_order_from_closed_or_canceled", return_value=None)

    with pytest.raises(RetryableOrderError):
        ex.fetch_order("abc", "BTC/USD:USD")


def test_krakenfutures_fetch_order_from_closed_or_canceled_returns_none(mocker, default_conf):
    """Return None when the exchange does not support order history endpoints."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    mocker.patch.object(ex, "exchange_has", return_value=False)

    res = ex._fetch_order_from_closed_or_canceled("abc", "BTC/USD:USD", {})
    assert res is None


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


def test_krakenfutures_validate_stakecurrency_calls_super(mocker, default_conf):
    """Test validate_stakecurrency calls the base implementation for non-EUR."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    base_validate = mocker.patch.object(Exchange, "validate_stakecurrency")

    ex.validate_stakecurrency("USD")
    assert base_validate.call_count == 1


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


def test_krakenfutures_get_balances_returns_for_non_usd_stake(mocker, default_conf):
    """Test get_balances returns early when stake currency is not USD."""
    conf = dict(default_conf)
    conf["stake_currency"] = "EUR"
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    sample = {"free": {"EUR": 10.0}, "used": {"EUR": 0.0}, "total": {"EUR": 10.0}}
    mocker.patch.object(Exchange, "get_balances", return_value=sample)

    res = ex.get_balances()
    assert res == sample
    assert "USD" not in res


def test_krakenfutures_get_balances_returns_when_flex_missing_or_invalid(mocker, default_conf):
    """Return original balances when flex data or USD extraction is missing."""
    conf = dict(default_conf)
    conf["stake_currency"] = "USD"
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    base_one = {"free": {}, "used": {}, "total": {}}
    base_two = {"free": {}, "used": {}, "total": {}}
    mocker.patch.object(Exchange, "get_balances", side_effect=[base_one, base_two])
    mocker.patch.object(ex, "_get_flex_account", side_effect=[None, {"availableMargin": 1.0}])
    mocker.patch.object(ex, "_extract_usd_from_flex", return_value=(None, 1.0))

    res = ex.get_balances()
    assert res == base_one

    res = ex.get_balances()
    assert res == base_two


def test_krakenfutures_get_balances_preserves_existing_usd(mocker, default_conf):
    """Keep existing USD free balance if higher than flex-derived value."""
    conf = dict(default_conf)
    conf["stake_currency"] = "USD"
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    sample = {
        "USD": {"free": 20.0, "used": 0.0, "total": 20.0},
        "free": {"USD": 20.0},
        "used": {"USD": 0.0},
        "total": {"USD": 20.0},
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
    assert res["free"]["USD"] == 20.0


def test_krakenfutures_sum_currencies_value_sums_valid_values(mocker, default_conf):
    """Sum currencies values, skipping invalid entries."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    currencies = {
        "USD": {"value": "10"},
        "EUR": {"value": 2.5},
        "BAD": {"value": ""},
        "NODICT": 3,
    }

    assert ex._sum_currencies_value(currencies) == 12.5


def test_krakenfutures_sum_currencies_value_returns_none_when_empty(mocker, default_conf):
    """Return None when no valid values are found."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    assert ex._sum_currencies_value(["not", "dict"]) is None
    assert ex._sum_currencies_value({"USD": {"value": ""}}) is None


def test_krakenfutures_get_flex_account_fetch_balance_error(mocker, default_conf):
    """Return None when fetch_balance fails while attempting to load flex data."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    mocker.patch.object(ex._api, "fetch_balance", side_effect=Exception("boom"), create=True)
    res = ex._get_flex_account({"free": {}, "used": {}, "total": {}}, None)
    assert res is None


def test_krakenfutures_extract_flex_from_raw_handles_invalid(mocker, default_conf):
    """Return None for malformed flex account structures."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    assert ex._extract_flex_from_raw(None) is None
    assert ex._extract_flex_from_raw({"info": "bad"}) is None
    assert ex._extract_flex_from_raw({"info": {"accounts": "bad"}}) is None


def test_krakenfutures_extract_usd_from_flex_fallbacks(mocker, default_conf):
    """Use currencies fallback and fill missing USD values."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")

    usd_free, usd_total = ex._extract_usd_from_flex(
        {"availableMargin": "5.0", "currencies": {"EUR": {"value": "6.0"}}}
    )
    assert usd_free == 5.0
    assert usd_total == 6.0

    usd_free, usd_total = ex._extract_usd_from_flex({"availableMargin": "7.0"})
    assert usd_free == 7.0
    assert usd_total == 7.0

    usd_free, usd_total = ex._extract_usd_from_flex({"balanceValue": "9.0"})
    assert usd_free == 9.0
    assert usd_total == 9.0


def test_krakenfutures_safe_float_invalid_returns_none(mocker, default_conf):
    """Return None for values that cannot be coerced to float."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    assert ex._safe_float("not-a-number") is None


def test_krakenfutures_get_funding_fees_futures_success(mocker, default_conf):
    """Use funding fee helper in futures mode."""
    conf = dict(default_conf)
    conf["trading_mode"] = TradingMode.FUTURES
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    helper = mocker.patch.object(ex, "_fetch_and_calculate_funding_fees", return_value=1.23)
    open_date = datetime.now(UTC)

    assert ex.get_funding_fees("BTC/USD:USD", 0.1, False, open_date) == 1.23
    helper.assert_called_once_with("BTC/USD:USD", 0.1, False, open_date)


def test_krakenfutures_get_funding_fees_futures_exchange_error(mocker, default_conf):
    """Return 0.0 when funding fee retrieval fails."""
    conf = dict(default_conf)
    conf["trading_mode"] = TradingMode.FUTURES
    ex = get_patched_exchange(mocker, conf, exchange="krakenfutures")

    mocker.patch.object(ex, "_fetch_and_calculate_funding_fees", side_effect=ExchangeError("fail"))

    assert ex.get_funding_fees("BTC/USD:USD", 0.1, False, None) == 0.0


def test_krakenfutures_get_funding_fees_spot_returns_zero(mocker, default_conf):
    """Return 0.0 outside futures mode without calling the helper."""
    ex = get_patched_exchange(mocker, default_conf, exchange="krakenfutures")
    helper = mocker.patch.object(ex, "_fetch_and_calculate_funding_fees")

    assert ex.get_funding_fees("BTC/USD:USD", 0.1, False, None) == 0.0
    helper.assert_not_called()
