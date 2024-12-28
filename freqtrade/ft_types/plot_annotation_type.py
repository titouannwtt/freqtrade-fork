from datetime import datetime

from typing_extensions import NotRequired, TypedDict


class MarkArea(TypedDict):
    start: NotRequired[str | datetime]
    end: NotRequired[str | datetime]
    y_start: NotRequired[float]
    y_end: NotRequired[float]
    color: NotRequired[str]
    label: NotRequired[str]
