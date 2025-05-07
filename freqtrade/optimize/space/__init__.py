from .decimalspace import SKDecimal, _adjust_discrete_uniform
from .optunaspaces import (
    DimensionProtocol,
    ft_CategoricalDistribution,
    ft_FloatDistribution,
    ft_IntDistribution,
)


# Alias for the distribution classes
Dimension = DimensionProtocol
Categorical = ft_CategoricalDistribution
Integer = ft_IntDistribution
Real = ft_FloatDistribution

__all__ = ["Categorical", "Dimension", "Integer", "Real", "SKDecimal", "_adjust_discrete_uniform"]
