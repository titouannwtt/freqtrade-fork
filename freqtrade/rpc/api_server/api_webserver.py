import logging
from copy import deepcopy

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException

from freqtrade.exceptions import OperationalException
from freqtrade.rpc.api_server.api_schemas import (
    ExchangeListResponse,
    HyperoptLossListResponse,
    StrategyListResponse,
    StrategyResponse,
)
from freqtrade.rpc.api_server.deps import get_config


logger = logging.getLogger(__name__)

# Private API, protected by authentication and webserver_mode dependency
router = APIRouter()


@router.get("/strategies", response_model=StrategyListResponse, tags=["strategy"])
def list_strategies(config=Depends(get_config)):
    from freqtrade.resolvers.strategy_resolver import StrategyResolver

    strategies = StrategyResolver.search_all_objects(
        config, False, config.get("recursive_strategy_search", False)
    )
    strategies = sorted(strategies, key=lambda x: x["name"])

    return {"strategies": [x["name"] for x in strategies]}


@router.get("/strategy/{strategy}", response_model=StrategyResponse, tags=["strategy"])
def get_strategy(strategy: str, config=Depends(get_config)):
    if ":" in strategy:
        raise HTTPException(status_code=500, detail="base64 encoded strategies are not allowed.")

    config_ = deepcopy(config)
    from freqtrade.resolvers.strategy_resolver import StrategyResolver

    try:
        strategy_obj = StrategyResolver._load_strategy(
            strategy, config_, extra_dir=config_.get("strategy_path")
        )
    except OperationalException:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "strategy": strategy_obj.get_strategy_name(),
        "code": strategy_obj.__source__,
        "timeframe": getattr(strategy_obj, "timeframe", None),
    }


@router.get("/exchanges", response_model=ExchangeListResponse, tags=[])
def list_exchanges(config=Depends(get_config)):
    from freqtrade.exchange import list_available_exchanges

    exchanges = list_available_exchanges(config)
    return {
        "exchanges": exchanges,
    }


@router.get(
    "/hyperoptloss", response_model=HyperoptLossListResponse, tags=["hyperopt", "webserver"]
)
def list_hyperoptloss(
    config=Depends(get_config),
):
    import textwrap

    from freqtrade.resolvers.hyperopt_resolver import HyperOptLossResolver

    loss_functions = HyperOptLossResolver.search_all_objects(config, False)
    loss_functions = sorted(loss_functions, key=lambda x: x["name"])

    return {
        "loss_functions": [
            {
                "name": x["name"],
                "description": textwrap.dedent((x["class"].__doc__ or "").strip()),
            }
            for x in loss_functions
        ]
    }
