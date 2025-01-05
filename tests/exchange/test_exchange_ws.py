import asyncio
import threading
from time import sleep
from unittest.mock import AsyncMock, MagicMock

from freqtrade.enums import CandleType
from freqtrade.exchange.exchange_ws import ExchangeWS


def test_exchangews_init(mocker):
    config = MagicMock()
    ccxt_object = MagicMock()
    mocker.patch("freqtrade.exchange.exchange_ws.ExchangeWS._start_forever", MagicMock())

    exchange_ws = ExchangeWS(config, ccxt_object)
    sleep(0.1)

    assert exchange_ws.config == config
    assert exchange_ws.ccxt_object == ccxt_object
    assert exchange_ws._thread.name == "ccxt_ws"
    assert exchange_ws._background_tasks == set()
    assert exchange_ws._klines_watching == set()
    assert exchange_ws._klines_scheduled == set()
    assert exchange_ws.klines_last_refresh == {}
    assert exchange_ws.klines_last_request == {}
    # Cleanup
    exchange_ws.cleanup()


def patch_eventloop_threading(exchange):
    is_init = False

    def thread_fuck():
        nonlocal is_init
        exchange._loop = asyncio.new_event_loop()
        is_init = True
        exchange._loop.run_forever()

    x = threading.Thread(target=thread_fuck, daemon=True)
    x.start()
    while not is_init:
        pass


async def test_exchangews_ohlcv(mocker, time_machine):
    config = MagicMock()
    ccxt_object = MagicMock()

    async def sleeper(*args, **kwargs):
        # pass
        await asyncio.sleep(1)
        return MagicMock()

    ccxt_object.watch_ohlcv = AsyncMock(side_effect=sleeper)
    ccxt_object.close = AsyncMock()
    time_machine.move_to("2024-11-01 01:00:00 +00:00")

    mocker.patch("freqtrade.exchange.exchange_ws.ExchangeWS._start_forever", MagicMock())

    exchange_ws = ExchangeWS(config, ccxt_object)
    patch_eventloop_threading(exchange_ws)
    try:
        assert exchange_ws._klines_watching == set()
        assert exchange_ws._klines_scheduled == set()

        exchange_ws.schedule_ohlcv("ETH/BTC", "1m", CandleType.SPOT)
        exchange_ws.schedule_ohlcv("XRP/BTC", "1m", CandleType.SPOT)
        await asyncio.sleep(0.5)

        assert exchange_ws._klines_watching == {
            ("ETH/BTC", "1m", CandleType.SPOT),
            ("XRP/BTC", "1m", CandleType.SPOT),
        }
        assert exchange_ws._klines_scheduled == {
            ("ETH/BTC", "1m", CandleType.SPOT),
            ("XRP/BTC", "1m", CandleType.SPOT),
        }
        await asyncio.sleep(0.1)
        assert ccxt_object.watch_ohlcv.call_count == 2
        ccxt_object.watch_ohlcv.reset_mock()

        time_machine.shift(timedelta(minutes=5))
        await asyncio.sleep(0.1)
        exchange_ws.schedule_ohlcv("ETH/BTC", "1m", CandleType.SPOT)
        # XRP/BTC should be cleaned up.
        assert exchange_ws._klines_watching == {
            ("ETH/BTC", "1m", CandleType.SPOT),
        }
        assert exchange_ws._klines_scheduled == {
            ("ETH/BTC", "1m", CandleType.SPOT),
            ("XRP/BTC", "1m", CandleType.SPOT),
        }

    finally:
        # Cleanup
        exchange_ws.cleanup()
