import decimal

from optuna.distributions import FloatDistribution


class SKDecimal(FloatDistribution):
    def __init__(
        self,
        low: float,
        high: float,
        step: float | None = None,
        decimals: int = 3,
        name=None,
    ):
        """
        FloatDistribution with a fixed step size.
        """
        if decimals is not None and step is not None:
            raise ValueError("You can only set one of decimals or step")
        # Convert decimals to step
        self.step = step or 1 / 10**decimals
        self.name = name

        super().__init__(
            low=_adjust_discrete_uniform(low, self.step),
            high=_adjust_discrete_uniform_high(low, high, self.step),
            step=self.step,
        )


def _adjust_discrete_uniform_high(low: float, high: float, step: float | None) -> float:
    if step:
        d_high = decimal.Decimal(str(high))
        d_low = decimal.Decimal(str(low))
        d_step = decimal.Decimal(str(step))

        d_r = d_high - d_low

        if d_r % d_step != decimal.Decimal("0"):
            high = float((d_r // d_step) * d_step + d_low)

    return high


def _adjust_discrete_uniform(val: float, step: float | None) -> float:
    if step:
        d_val = decimal.Decimal(str(val))
        d_step = decimal.Decimal(str(step))

        if d_val % d_step != decimal.Decimal("0"):
            val = float((d_val // d_step) * d_step)

    return val
