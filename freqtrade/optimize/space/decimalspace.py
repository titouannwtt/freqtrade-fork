from optuna.distributions import FloatDistribution


class SKDecimal(FloatDistribution):
    def __init__(
        self,
        low: float,
        high: float,
        step: float | None = None,
        decimals: int | None = 3,
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
            low=low,
            high=high,
            step=self.step,
        )
