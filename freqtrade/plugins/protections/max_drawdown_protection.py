import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from freqtrade.constants import Config, LongShort
from freqtrade.data.metrics import calculate_max_drawdown
from freqtrade.persistence import Trade
from freqtrade.plugins.protections import IProtection, ProtectionReturn


logger = logging.getLogger(__name__)


class MaxDrawdown(IProtection):
    has_global_stop: bool = True
    has_local_stop: bool = False

    def __init__(self, config: Config, protection_config: dict[str, Any]) -> None:
        super().__init__(config, protection_config)

        self._trade_limit = protection_config.get("trade_limit", 1)
        self._max_allowed_drawdown = protection_config.get("max_allowed_drawdown", 0.0)
        # TODO: Implement checks to limit max_drawdown to sensible values

    def short_desc(self) -> str:
        """
        Short method description - used for startup-messages
        """
        return (
            f"{self.name} - Max drawdown protection, stop trading if drawdown is > "
            f"{self._max_allowed_drawdown} within {self.lookback_period_str}."
        )

    def _reason(self, drawdown: float) -> str:
        """
        LockReason to use
        """
        return (
            f"{drawdown} passed {self._max_allowed_drawdown} in {self.lookback_period_str}, "
            f"locking {self.unlock_reason_time_element}."
        )

    def _max_drawdown(self, date_now: datetime, starting_balance: float) -> ProtectionReturn | None:
        """
        Evaluate recent trades for drawdown ...
        """
        look_back_until = date_now - timedelta(minutes=self._lookback_period)

        # Get all closed trades to calculate balance at the start of the window
        all_closed_trades = Trade.get_trades_proxy(is_open=False)

        trades_in_window = []
        profit_before_window = 0.0
        for trade in all_closed_trades:
            if trade.close_date:
                # Ensure close_date is aware for comparison
                close_date = (trade.close_date.replace(tzinfo=UTC)
                              if trade.close_date.tzinfo is None else trade.close_date)
                if close_date > look_back_until:
                    trades_in_window.append(trade)
                else:
                    profit_before_window += (trade.close_profit_abs or 0.0)

        if len(trades_in_window) < self._trade_limit:
            # Not enough trades in the relevant period
            return None

        # Calculate actual balance at the start of the lookback window
        actual_starting_balance = starting_balance + profit_before_window

        trades_df = pd.DataFrame([trade.to_json() for trade in trades_in_window])

        # Drawdown is always positive
        try:
            # Use absolute profit calculation with the actual balance at window start.
            drawdown_obj = calculate_max_drawdown(
                trades_df,
                value_col="profit_abs",
                starting_balance=actual_starting_balance,
                relative=True
            )
            # Use relative drawdown to compare against max_allowed_drawdown percentage
            drawdown = drawdown_obj.relative_account_drawdown
        except ValueError:
            return None

        if drawdown > self._max_allowed_drawdown:
            self.log_once(
                f"Trading stopped due to Max Drawdown {drawdown:.2f} > {self._max_allowed_drawdown}"
                f" within {self.lookback_period_str}.",
                logger.info,
            )

            until = self.calculate_lock_end(trades_in_window)

            return ProtectionReturn(
                lock=True,
                until=until,
                reason=self._reason(drawdown),
            )

        return None

    def global_stop(
        self, date_now: datetime, side: LongShort, starting_balance: float = 0.0
    ) -> ProtectionReturn | None:
        """
        Stops trading (position entering) for all pairs
        This must evaluate to true for the whole period of the "cooldown period".
        :return: Tuple of [bool, until, reason].
            If true, all pairs will be locked with <reason> until <until>
        """
        return self._max_drawdown(date_now, starting_balance)

    def stop_per_pair(
        self, pair: str, date_now: datetime, side: LongShort, starting_balance: float = 0.0
    ) -> ProtectionReturn | None:
        """
        Stops trading (position entering) for this pair
        This must evaluate to true for the whole period of the "cooldown period".
        :return: Tuple of [bool, until, reason].
            If true, this pair will be locked with <reason> until <until>
        """
        return None
