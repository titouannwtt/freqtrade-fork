from datetime import datetime
from logging import Handler
from typing import Any

from rich.text import Text


class FtRichHandler(Handler):
    def __init__(self, console, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._console = console

    def emit(self, record):
        try:
            msg = self.format(record)
            # Format log message
            log_time = Text(
                datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
                style="gray46",
            )
            name = Text(record.name)
            log_level = Text(record.levelname, style=f"logging.level.{record.levelname.lower()}")
            gray_sep = Text(" - ", style="gray46")

            self._console.print(
                Text() + log_time + gray_sep + name + gray_sep + log_level + gray_sep + msg
            )

            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
