from contextlib import AbstractContextManager
from typing import Protocol

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from freqtrade.util.rich_progress import CustomProgress


class ProgressLike(Protocol, AbstractContextManager["ProgressLike"]):
    def add_task(self, description: str, *args, **kwargs) -> TaskID: ...

    def update(self, task_id: TaskID, *, advance: float | None = None, **kwargs): ...


def retrieve_progress_tracker(pt: ProgressLike | None) -> ProgressLike:
    if pt is None:
        return get_progress_tracker()
    return pt


def get_progress_tracker(**kwargs) -> ProgressLike:
    """
    Get progress Bar with custom columns.
    """
    return CustomProgress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        "•",
        TimeElapsedColumn(),
        "•",
        TimeRemainingColumn(),
        expand=True,
        **kwargs,
    )
