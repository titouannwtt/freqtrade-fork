import logging
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException

from freqtrade.rpc.api_server.api_schemas import PairHistory, PairHistoryRequest
from freqtrade.rpc.api_server.deps import get_config, get_exchange
from freqtrade.rpc.rpc import RPC


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/pair_history", response_model=PairHistory, tags=["candle data"])
def pair_history(
    pair: str,
    timeframe: str,
    timerange: str,
    strategy: str,
    freqaimodel: str | None = None,
    config=Depends(get_config),
    exchange=Depends(get_exchange),
):
    # The initial call to this endpoint can be slow, as it may need to initialize
    # the exchange class.
    config = deepcopy(config)
    config.update(
        {
            "timeframe": timeframe,
            "strategy": strategy,
            "timerange": timerange,
            "freqaimodel": freqaimodel if freqaimodel else config.get("freqaimodel"),
        }
    )
    try:
        return RPC._rpc_analysed_history_full(config, pair, timeframe, exchange, None)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/pair_history", response_model=PairHistory, tags=["candle data"])
def pair_history_filtered(
    payload: PairHistoryRequest, config=Depends(get_config), exchange=Depends(get_exchange)
):
    # The initial call to this endpoint can be slow, as it may need to initialize
    # the exchange class.
    config = deepcopy(config)
    config.update(
        {
            "timeframe": payload.timeframe,
            "strategy": payload.strategy,
            "timerange": payload.timerange,
            "freqaimodel": (
                payload.freqaimodel if payload.freqaimodel else config.get("freqaimodel")
            ),
        }
    )
    try:
        return RPC._rpc_analysed_history_full(
            config, payload.pair, payload.timeframe, exchange, payload.columns
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
