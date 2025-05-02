from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AnnotationType(BaseModel):
    type: Literal["area"]
    start: None | str | datetime = None
    end: None | str | datetime = None
    y_start: None | float = None
    y_end: None | float = None
    color: None | str = None
    label: None | str = None
