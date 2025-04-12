from collections.abc import Callable

from cachetools import TTLCache, cached


class LoggingMixin:
    """
    Logging Mixin
    Shows similar messages only once every `refresh_period`.
    """

    # Disable INFO output when False
    show_info_output = True

    def __init__(self, logger, refresh_period: int = 3600):
        """
        :param refresh_period: in seconds - Show identical messages in this intervals
        """
        self.logger = logger
        self.refresh_period = refresh_period
        self._log_cache: TTLCache = TTLCache(maxsize=1024, ttl=self.refresh_period)

    def log_once(self, message: str, logmethod: Callable) -> None:
        """
        Logs message - not more often than "refresh_period" to avoid log spamming
        Logs the log-message as debug as well to simplify debugging.
        :param message: String containing the message to be sent to the function.
        :param logmethod: Function that'll be called. Most likely `logger.info`.
        :return: None.
        """

        @cached(cache=self._log_cache)
        def _log_once(message: str):
            logmethod(message)

        # Log as debug first
        self.logger.debug(message)

        # Determine if this is an INFO level message
        is_info_message = getattr(logmethod, "__name__", "") == "info"

        # For INFO messages, respect show_info_output flag
        if not is_info_message or self.show_info_output:
            _log_once(message)
