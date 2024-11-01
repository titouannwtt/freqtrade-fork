import asyncio
import datetime
import io
import re
import sys
import zipfile
from datetime import timedelta

import aiohttp
import pandas as pd
import pytest

from freqtrade.enums import CandleType
from freqtrade.exchange.binance_public_data import (
    BadHttpStatus,
    fetch_ohlcv,
    get_daily_ohlcv,
    symbol_ccxt_to_binance,
    zip_name,
)
from freqtrade.util.datetime_helpers import dt_ts, dt_utc


@pytest.fixture(scope="module")
def event_loop_policy(request):
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    else:
        return asyncio.DefaultEventLoopPolicy()


# spot klines archive csv file format, the futures/um klines don't have the header line
#
# open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore  # noqa: E501
# 1698364800000,34161.6,34182.5,33977.4,34024.2,409953,1698368399999,1202.97118037,15095,192220,564.12041453,0  # noqa: E501
# 1698368400000,34024.2,34060.1,33776.4,33848.4,740960,1698371999999,2183.75671155,23938,368266,1085.17080793,0  # noqa: E501
# 1698372000000,33848.5,34150.0,33815.1,34094.2,390376,1698375599999,1147.73267094,13854,231446,680.60405822,0  # noqa: E501


def make_daily_df(date, timeframe):
    start = dt_utc(date.year, date.month, date.day)
    end = start + timedelta(days=1)
    date_col = pd.date_range(start, end, freq=timeframe.replace("m", "min"), inclusive="left")
    cols = (
        "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,"
        "taker_buy_quote_volume,ignore"
    )
    df = pd.DataFrame(columns=cols.split(","), dtype=float)
    df["open_time"] = date_col.astype("int64") // 10**6
    df["open"] = df["high"] = df["low"] = df["close"] = df["volume"] = 1.0
    return df


def make_daily_zip(asset_type, symbol, timeframe, date) -> bytes:
    df = make_daily_df(date, timeframe)
    if asset_type == "spot":
        header = True
    elif asset_type == "futures/um":
        header = None
    else:
        raise ValueError
    csv = df.to_csv(index=False, header=header)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        zipf.writestr(zip_name(symbol, timeframe, date), csv)
    return zip_buffer.getvalue()


class MockResponse:
    def __init__(self, content, status, reason=""):
        self._content = content
        self.status = status
        self.reason = reason

    async def read(self):
        return self._content

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self


def make_response_from_url(start_date, end_date):
    def make_response(url):
        pattern = (
            r"https://data.binance.vision/data/(?P<asset_type>spot|futures/um)/daily/klines/"
            r"(?P<symbol>.*?)/(?P<timeframe>.*?)/(?P=symbol)-(?P=timeframe)-"
            r"(?P<date>\d{4}-\d{2}-\d{2}).zip"
        )
        m = re.match(pattern, url)
        if not m:
            return MockResponse(content="", status=404)

        date = datetime.datetime.strptime(m["date"], "%Y-%m-%d").date()
        if date < start_date or date > end_date:
            return MockResponse(content="", status=404)

        zip_file = make_daily_zip(m["asset_type"], m["symbol"], m["timeframe"], date)
        return MockResponse(content=zip_file, status=200)

    return make_response


@pytest.mark.parametrize(
    "candle_type,since,until,first_date,last_date,stop_on_404",
    [
        (
            CandleType.SPOT,
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 2),
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 1, 23),
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 1, 23, 59, 59),
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 1, 23),
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 5),
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 3, 23),
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2019, 1, 1),
            dt_utc(2020, 1, 5),
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 3, 23),
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2019, 1, 1),
            dt_utc(2019, 1, 5),
            None,
            None,
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2021, 1, 1),
            dt_utc(2021, 1, 5),
            None,
            None,
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2020, 1, 2),
            None,
            dt_utc(2020, 1, 2),
            dt_utc(2020, 1, 3, 23),
            False,
        ),
        (
            CandleType.SPOT,
            dt_utc(2019, 1, 1),
            dt_utc(2020, 1, 5),
            None,
            None,
            True,
        ),
        (
            CandleType.SPOT,
            dt_utc(2020, 1, 5),
            dt_utc(2020, 1, 1),
            None,
            None,
            False,
        ),
        (
            CandleType.FUTURES,
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 1, 23, 59, 59),
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 1, 23),
            False,
        ),
        (
            CandleType.INDEX,
            dt_utc(2020, 1, 1),
            dt_utc(2020, 1, 1, 23, 59, 59),
            None,
            None,
            False,
        ),
    ],
)
async def test_fetch_ohlcv(mocker, candle_type, since, until, first_date, last_date, stop_on_404):
    history_start = dt_utc(2020, 1, 1).date()
    history_end = dt_utc(2020, 1, 3).date()
    timeframe = "1h"
    pair = "BTCUSDT"

    since_ms = dt_ts(since)
    until_ms = dt_ts(until)

    mocker.patch(
        "aiohttp.ClientSession.get", side_effect=make_response_from_url(history_start, history_end)
    )

    df = await fetch_ohlcv(candle_type, pair, timeframe, since_ms, until_ms, stop_on_404)

    if df.empty:
        assert first_date is None and last_date is None
    else:
        assert candle_type in [CandleType.SPOT, CandleType.FUTURES]
        assert df["date"].iloc[0] == first_date
        assert df["date"].iloc[-1] == last_date


async def test_fetch_ohlcv_exc(mocker):
    timeframe = "1h"
    pair = "BTCUSDT"

    since_ms = dt_ts(dt_utc(2020, 1, 1))
    until_ms = dt_ts(dt_utc(2020, 1, 2))

    mocker.patch("aiohttp.ClientSession.get", side_effect=RuntimeError)

    df = await fetch_ohlcv(CandleType.SPOT, pair, timeframe, since_ms, until_ms)

    assert df.empty


async def test_get_daily_ohlcv(mocker, testdatadir):
    symbol = "BTCUSDT"
    timeframe = "1h"
    date = dt_utc(2024, 10, 28).date()
    first_date = dt_utc(2024, 10, 28)
    last_date = dt_utc(2024, 10, 28, 23)

    async with aiohttp.ClientSession() as session:
        path = testdatadir / "binance/binance_public_data/spot-klines-BTCUSDT-1h-2024-10-28.zip"
        mocker.patch("aiohttp.ClientSession.get", return_value=MockResponse(path.read_bytes(), 200))
        df = await get_daily_ohlcv("spot", symbol, timeframe, date, session)
        assert df["date"].iloc[0] == first_date
        assert df["date"].iloc[-1] == last_date

        path = (
            testdatadir / "binance/binance_public_data/futures-um-klines-BTCUSDT-1h-2024-10-28.zip"
        )
        mocker.patch("aiohttp.ClientSession.get", return_value=MockResponse(path.read_bytes(), 200))
        df = await get_daily_ohlcv("futures/um", symbol, timeframe, date, session)
        assert df["date"].iloc[0] == first_date
        assert df["date"].iloc[-1] == last_date

        mocker.patch("aiohttp.ClientSession.get", return_value=MockResponse(b"", 404))
        df = await get_daily_ohlcv("spot", symbol, timeframe, date, session)
        assert df is None

        mocker.patch("aiohttp.ClientSession.get", return_value=MockResponse(b"", 500))
        mocker.patch("asyncio.sleep")
        df = await get_daily_ohlcv("spot", symbol, timeframe, date, session)
        assert isinstance(df, BadHttpStatus)

        mocker.patch("aiohttp.ClientSession.get", return_value=MockResponse(b"nop", 200))
        df = await get_daily_ohlcv("spot", symbol, timeframe, date, session)
        assert isinstance(df, zipfile.BadZipFile)


def test_symbol_ccxt_to_binance():
    assert symbol_ccxt_to_binance("BTC/USDT") == "BTCUSDT"
    assert symbol_ccxt_to_binance("BTC/USDT:USDT") == "BTCUSDT"
    with pytest.raises(ValueError):
        assert symbol_ccxt_to_binance("BTC:USDT:USDT") == "BTCUSDT"
