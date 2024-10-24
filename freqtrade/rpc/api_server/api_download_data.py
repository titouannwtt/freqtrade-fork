import logging
from copy import deepcopy

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.exceptions import HTTPException

from freqtrade.constants import Config
from freqtrade.exceptions import OperationalException
from freqtrade.persistence import FtNoDBContext
from freqtrade.rpc.api_server.api_pairlists import handleExchangePayload
from freqtrade.rpc.api_server.api_schemas import BgJobStarted, DownloadDataPayload
from freqtrade.rpc.api_server.deps import get_config, get_exchange
from freqtrade.rpc.api_server.webserver_bgwork import ApiBG


logger = logging.getLogger(__name__)

# Private API, protected by authentication and webserver_mode dependency
router = APIRouter(tags=["download-data", "webserver"])


def __run_download(job_id: str, config_loc: Config):
    try:
        ApiBG.jobs[job_id]["is_running"] = True
        from freqtrade.data.history.history_utils import download_data

        with FtNoDBContext():
            exchange = get_exchange(config_loc)

            download_data(config_loc, exchange)
            # ApiBG.jobs[job_id]["result"] = {

            # }
            ApiBG.jobs[job_id]["status"] = "success"
    except (OperationalException, Exception) as e:
        logger.exception(e)
        ApiBG.jobs[job_id]["error"] = str(e)
        ApiBG.jobs[job_id]["status"] = "failed"
    finally:
        ApiBG.jobs[job_id]["is_running"] = False
        ApiBG.download_data_running = False


@router.post("/download_data", response_model=BgJobStarted)
def pairlists_evaluate(
    payload: DownloadDataPayload, background_tasks: BackgroundTasks, config=Depends(get_config)
):
    if ApiBG.download_data_running:
        raise HTTPException(status_code=400, detail="Pairlist evaluation is already running.")
    config_loc = deepcopy(config)
    config_loc["stake_currency"] = payload.stake_currency
    config_loc["pairs"] = payload.pairs
    config_loc["timeframes"] = payload.timeframes
    handleExchangePayload(payload, config_loc)
    print(payload)

    job_id = ApiBG.get_job_id()

    ApiBG.jobs[job_id] = {
        "category": "download_data",
        "status": "pending",
        "progress": None,
        "is_running": False,
        "result": {},
        "error": None,
    }
    background_tasks.add_task(__run_download, job_id, config_loc)
    ApiBG.download_data_running = True

    return {
        "status": "Data Download started in background.",
        "job_id": job_id,
    }
