"""
Fetch daily-archived OHLCV data from https://data.binance.vision/
"""

import asyncio
import datetime
import io
import itertools
import logging
import zipfile

import aiohttp
import pandas as pd
from pandas import DataFrame

from freqtrade.enums import CandleType
from freqtrade.util.datetime_helpers import dt_from_ts, dt_now


logger = logging.getLogger(__name__)


class BadHttpStatus(Exception):
    """Not 200/404"""

    pass


async def fetch_ohlcv(
    candle_type: CandleType, pair: str, timeframe: str, since_ms: int, until_ms: int | None
) -> DataFrame:
    """
    Fetch OHLCV data from https://data.binance.vision/
    :candle_type: Currently only spot and futures are supported
    :param until_ms: `None` indicates the timestamp of the latest available data
    :return: None if no data available in the time range
    """
    if candle_type == CandleType.SPOT:
        asset_type = "spot"
    elif candle_type == CandleType.FUTURES:
        asset_type = "futures/um"
    else:
        raise ValueError(f"Unsupported CandleType: {candle_type}")
    symbol = symbol_ccxt_to_binance(pair)
    start = dt_from_ts(since_ms)
    end = dt_from_ts(until_ms) if until_ms else dt_now()

    # We use two days ago as the last available day because the daily archives are daily uploaded
    # and have several hours delay
    last_available_date = dt_now() - datetime.timedelta(days=2)
    end = min(end, last_available_date)
    if start >= end:
        return DataFrame()
    return await _fetch_ohlcv(asset_type, symbol, timeframe, start, end)


def symbol_ccxt_to_binance(symbol: str) -> str:
    """
    Convert ccxt symbol notation to binance notation
    e.g. BTC/USDT -> BTCUSDT, BTC/USDT:USDT -> BTCUSDT
    """
    if ":" in symbol:
        parts = symbol.split()
        if len(parts) != 2:
            raise ValueError(f"Cannot recognize symbol: {symbol}")
        return parts[0].replace("/", "")
    else:
        return symbol.replace("/", "")


def concat(dfs) -> DataFrame:
    if all(df is None for df in dfs):
        return DataFrame()
    else:
        return pd.concat(dfs)


async def _fetch_ohlcv(asset_type, symbol, timeframe, start, end) -> DataFrame:
    dfs: list[DataFrame | None] = []

    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        coroutines = [
            get_daily_ohlcv(asset_type, symbol, timeframe, date, session)
            for date in date_range(start, end)
        ]
        # the HTTP connections has been throttled by TCPConnector
        for batch in itertools.batched(coroutines, 1000):
            results = await asyncio.gather(*batch)
            for result in results:
                if isinstance(result, BaseException):
                    logger.warning(f"An exception raised: : {result}")
                    # Directly return the existing data, do not allow the gap
                    # between the data
                    return concat(dfs)
                else:
                    dfs.append(result)
    return concat(dfs)


def date_range(start: datetime.date, end: datetime.date):
    date = start
    while date <= end:
        yield date
        date += datetime.timedelta(days=1)


def format_date(date: datetime.date) -> str:
    return date.strftime("%Y-%m-%d")


def zip_name(symbol: str, timeframe: str, date: datetime.date) -> str:
    return f"{symbol}-{timeframe}-{format_date(date)}.zip"


async def get_daily_ohlcv(
    asset_type: str,
    symbol: str,
    timeframe: str,
    date: datetime.date,
    session: aiohttp.ClientSession,
    retry_count: int = 3,
) -> DataFrame | None:
    """
    Get daily OHLCV from https://data.binance.vision
    See https://github.com/binance/binance-public-data
    """

    # example urls:
    # https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1s/BTCUSDT-1s-2023-10-27.zip
    # https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2023-10-27.zip
    url = (
        f"https://data.binance.vision/data/{asset_type}/daily/klines/{symbol}/{timeframe}/"
        f"{zip_name(symbol, timeframe, date)}"
    )

    logger.debug(f"download data from binance: {url}")

    retry = 0
    while True:
        if retry > 0:
            sleep_secs = retry * 0.5
            logger.debug(
                f"[{retry}/{retry_count}] retry to download {url} after {sleep_secs} seconds"
            )
            await asyncio.sleep(sleep_secs)
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    logger.debug(f"Successfully downloaded {url}")
                    with zipfile.ZipFile(io.BytesIO(content)) as zipf:
                        with zipf.open(zipf.namelist()[0]) as csvf:
                            # https://github.com/binance/binance-public-data/issues/283
                            first_byte = csvf.read(1)[0]
                            if chr(first_byte).isdigit():
                                header = None
                            else:
                                header = 0
                            csvf.seek(0)

                            df = pd.read_csv(
                                csvf,
                                usecols=[0, 1, 2, 3, 4, 5],
                                names=["date", "open", "high", "low", "close", "volume"],
                                header=header,
                            )
                            df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
                            return df
                elif resp.status == 404:
                    logger.warning(f"No data available for {symbol} in {format_date(date)}")
                    return None
                else:
                    raise BadHttpStatus(f"{resp.status} - {resp.reason}")
        except Exception as e:
            retry += 1
            if retry >= retry_count:
                logger.warning(f"Failed to get data from {url}: {e}")
                raise
