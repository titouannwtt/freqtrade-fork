from datetime import datetime
from logging import Handler

from rich.console import Console
from rich.text import Text
from rich.traceback import Traceback


class FtRichHandler(Handler):
    """
    Basic colorized logging handler using Rich.
    Does not support all features of the standard logging handler, and uses a hard-coded log format
    """

    def __init__(self, console: Console, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._console = console

    def emit(self, record):
        try:
            msg = self.format(record)
            # Format log message
            log_time = Text(
                datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
            )
            name = Text(record.name, style="violet")
            log_level = Text(record.levelname, style=f"logging.level.{record.levelname.lower()}")
            gray_sep = Text(" - ", style="gray46")

            self._console.print(
                Text() + log_time + gray_sep + name + gray_sep + log_level + gray_sep + msg
            )
            tb = None
            if record.exc_info:
                exc_type, exc_value, exc_traceback = record.exc_info
                tb = Traceback.from_exception(exc_type, exc_value, exc_traceback)
                self._console.print(tb)

            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
