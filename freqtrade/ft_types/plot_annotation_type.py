from datetime import datetime
from typing import Literal, Required

from pydantic import TypeAdapter
from typing_extensions import TypedDict


class _BaseAnnotationType(TypedDict, total=False):
    type: Required[Literal["area", "line"]]
    start: str | datetime
    end: str | datetime
    y_start: float
    y_end: float
    color: str
    label: str
    z_level: int


class AreaAnnotationType(_BaseAnnotationType, total=False):
    type: Literal["area"]


class LinenAnnotationType(_BaseAnnotationType, total=False):
    type: Literal["line"]
    width: int
    line_style: Literal["solid", "dashed", "dotted"]


AnnotationType = AreaAnnotationType | LinenAnnotationType

AnnotationTypeTA = TypeAdapter(AnnotationType)
