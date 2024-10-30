"""
This file is meant to test the OHLCV download performance between
from rest API and from data.binance.vision

using https://data.binance.vision:
{Task(trading_mode='spot', pair='ETH/USDT', timeframe='1s', timerange='20240101-20240501'): 28.26517415046692,
 Task(trading_mode='spot', pair='ETH/USDT', timeframe='1m', timerange='20180101-20240101'): 17.766807794570923,
 Task(trading_mode='spot', pair='ETH/USDT', timeframe='5m', timerange='20180101-20240101'): 11.347743034362793,
 Task(trading_mode='futures', pair='ETH/USDT:USDT', timeframe='1m', timerange='20200101-20240101'): 15.93356990814209,
 Task(trading_mode='futures', pair='ETH/USDT:USDT', timeframe='5m', timerange='20200101-20240101'): 10.111769914627075}

using rest API:
{Task(trading_mode='spot', pair='ETH/USDT', timeframe='1s', timerange='20240101-20240501'): 257.9407958984375,
 Task(trading_mode='spot', pair='ETH/USDT', timeframe='1m', timerange='20180101-20240101'): 86.42260813713074,
 Task(trading_mode='spot', pair='ETH/USDT', timeframe='5m', timerange='20180101-20240101'): 20.111007928848267,
 Task(trading_mode='futures', pair='ETH/USDT:USDT', timeframe='1m', timerange='20200101-20240101'): 537.5525922775269,
 Task(trading_mode='futures', pair='ETH/USDT:USDT', timeframe='5m', timerange='20200101-20240101'): 111.13234090805054}

compare:
spot-1s: 9X
spot-1m: 5X
spot-5m: 2X
futures-1m: 34X
futures-5m: 11X

Usage:
    # first switch to the branch you want to test
    python tests/exchange/binance_ohlcv_compare.py
"""
# flake8: noqa: E501

import pprint
import subprocess
import time
from collections import namedtuple
from pathlib import Path


def rm_feather(data_dir, exchange, trading_mode, pair, timeframe):
    data_dir = Path(data_dir)
    is_futures = trading_mode == "futures"
    file_name = (
        pair.replace("/", "_").replace(":", "_")
        + "-"
        + timeframe
        + ("-futures" if is_futures else "")
        + ".feather"
    )
    file_dir = data_dir / exchange / ("futures" if is_futures else ".")
    file_path = file_dir / file_name
    file_path.unlink(missing_ok=True)


def download_data(trading_mode, exchange, pair, timeframe, timerange):
    cmd = (
        f"freqtrade download-data --trading-mode {trading_mode} --exchange {exchange} "
        f"--pairs {pair} --timeframe {timeframe} --timerange {timerange}"
    )
    start = time.time()
    subprocess.run(cmd, shell=True)  # noqa: S602
    end = time.time()
    elapsed = end - start

    print("-----")
    print(trading_mode, timeframe, timerange, elapsed)
    print("-----")

    return elapsed


def main():
    Task = namedtuple("Task", "trading_mode, pair, timeframe, timerange")
    tasks = [
        Task(
            "spot",
            "ETH/USDT",
            "1s",
            "20240101-20240501",
        ),
        Task(
            "spot",
            "ETH/USDT",
            "1m",
            "20180101-20240101",
        ),
        Task(
            "spot",
            "ETH/USDT",
            "5m",
            "20180101-20240101",
        ),
        Task(
            "futures",
            "ETH/USDT:USDT",
            "1m",
            "20200101-20240101",
        ),
        Task(
            "futures",
            "ETH/USDT:USDT",
            "5m",
            "20200101-20240101",
        ),
    ]

    exchange = "binance"
    data_dir = "user_data/data"

    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(data_dir)

    result = {}

    for task in tasks:
        rm_feather(
            data_dir=data_dir,
            exchange=exchange,
            trading_mode=task.trading_mode,
            pair=task.pair,
            timeframe=task.timeframe,
        )
        elapsed = download_data(
            trading_mode=task.trading_mode,
            exchange=exchange,
            pair=task.pair,
            timeframe=task.timeframe,
            timerange=task.timerange,
        )
        result[task] = elapsed

    pprint.pp(result)


if __name__ == "__main__":
    main()
