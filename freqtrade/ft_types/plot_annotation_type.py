from datetime import datetime
from typing import Literal

from typing_extensions import NotRequired, TypedDict


class AnnotationType(TypedDict):
    type: Literal["area"]
    start: NotRequired[str | datetime]
    end: NotRequired[str | datetime]
    y_start: NotRequired[float]
    y_end: NotRequired[float]
    color: NotRequired[str]
    label: NotRequired[str]
