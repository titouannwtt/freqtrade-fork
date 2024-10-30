"""
Check if the earliest klines from rest API have its counterpart on https://data.binance.vision
Not expected to run in CI, manually run from shell:

    TEST_BINANCE_COMPARE_OHLCV=1 pytest tests/exchange_online/test_binance_compare_ohlcv.py

Until 2024-10-30, there are three usdt-m futures symbols "lack" data
All SPOT symbols are good.

BTCUSDT-1m                                          113 days
ARCHIVE: 2019-12-31 00:00:00 │ 2024-10-30 02:51:00 │ 2541772
API:     2019-09-08 17:57:00 │ 2024-10-30 03:11:00 │ 2704874

ETHUSDT                                              34 days
ARCHIVE: 2019-12-31 00:00:00 │ 2020-02-29 23:59:00 │   87840
API:     2019-11-27 07:45:00 │ 2020-03-01 11:03:00 │  136999

BCHUSDT                                              12 days
ARCHIVE: 2019-12-31 00:00:00 │ 2020-02-29 23:59:00 │   87840
API:     2019-12-19 08:57:00 │ 2020-03-01 06:55:00 │  104999
"""

import asyncio
import os

import aiohttp
import pytest

from freqtrade.exchange.binance_public_data import zip_url
from freqtrade.util.datetime_helpers import dt_from_ts


class Check:
    def __init__(self, asset_type, timeframe):
        self.asset_type = asset_type
        self.timeframe = timeframe
        self.klines_endpoint = "https://api.binance.com/api/v3/klines"
        self.exchange_endpoint = "https://api.binance.com/api/v3/exchangeInfo"
        self.mismatch = set()

        if asset_type == "futures/um":
            self.klines_endpoint = "https://fapi.binance.com/fapi/v1/klines"
            self.exchange_endpoint = "https://fapi.binance.com/fapi/v1/exchangeInfo"

    async def check_one_symbol(self, symbol):
        async with self.session.get(
            self.klines_endpoint, params=dict(symbol=symbol, interval=self.timeframe, startTime=0)
        ) as resp:
            resp.raise_for_status()
            json = await resp.json()
            first_kline = json[0]
            first_kline_ts = first_kline[0]
            date = dt_from_ts(first_kline_ts).date()

        archive_url = zip_url(self.asset_type, symbol=symbol, timeframe=self.timeframe, date=date)
        async with self.session.get(
            archive_url, params=dict(symbol=symbol, interval=self.timeframe, startTime=0)
        ) as resp:
            if resp.status != 200:
                self.mismatch.add(symbol)
                print(
                    f"{resp.status} API first kline: {dt_from_ts(first_kline_ts).isoformat()}  "
                    f"{archive_url}"
                )
                web_url = archive_url.rsplit("/", 1)[0].replace(
                    "https://data.binance.vision/", "https://data.binance.vision/?prefix="
                )
                print(f"Check {web_url}")

    async def get_symbols(self):
        async with self.session.get(self.exchange_endpoint) as resp:
            resp.raise_for_status()
            json = await resp.json()
            symbols = [
                symbol["symbol"]
                for symbol in json["symbols"]
                if not symbol["status"] == "PENDING_TRADING"
            ]
            return symbols

    async def run(self) -> list:
        async with aiohttp.ClientSession() as session:
            self.session = session
            symbols = await self.get_symbols()
            await asyncio.gather(*[self.check_one_symbol(symbol) for symbol in symbols])
            return self.mismatch


@pytest.mark.skipif(
    not bool(os.environ.get("TEST_BINANCE_COMPARE_OHLCV")),
    reason="Simply to demonstrate the availabity of the archive endpoint",
)
async def test_binance_compare_ohlcv():
    futures_mismatch = await Check("futures/um", "1m").run()
    assert futures_mismatch == set(["BTCUSDT", "ETHUSDT", "BCHUSDT"])

    spot_mismatch = await Check("spot", "1m").run()
    assert not spot_mismatch

    assert 0
