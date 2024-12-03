"""
SharpeHyperOptLoss

This module defines the alternative HyperOptLoss class which can be used for
Hyperoptimization.
"""

from datetime import datetime

from pandas import DataFrame

from freqtrade.constants import Config
from freqtrade.data.metrics import calculate_sharpe
from freqtrade.optimize.hyperopt import IHyperOptLoss
from freqtrade.util.dry_run_wallet import get_dry_run_wallet


class SharpeHyperOptLoss(IHyperOptLoss):
    """
    Defines the loss function for hyperopt.

    This implementation uses the Sharpe Ratio calculation.
    """

    @staticmethod
    def hyperopt_loss_function(
        results: DataFrame,
        trade_count: int,
        min_date: datetime,
        max_date: datetime,
        config: Config,
        *args,
        **kwargs,
    ) -> float:
        """
        Objective function, returns smaller number for more optimal results.

        Uses Sharpe Ratio calculation.
        """
        starting_balance = get_dry_run_wallet(config)
        sharp_ratio = calculate_sharpe(results, min_date, max_date, starting_balance)
        # print(expected_returns_mean, up_stdev, sharp_ratio)
        return -sharp_ratio
