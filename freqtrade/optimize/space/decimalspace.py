from math import log10

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
            low=round(low, int(log10(1 / self.step))) if self.step < 1 else low,
            high=round(high, int(log10(1 / self.step))) if self.step < 1 else high,
            step=self.step,
        )
