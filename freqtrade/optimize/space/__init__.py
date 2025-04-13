# from skopt.space import Categorical, Dimension, Integer, Real  # noqa: F401
from .decimalspace import SKDecimal  # noqa: F401
from .optunaspaces import DimensionProtocol as Dimension  # noqa: F401
from .optunaspaces import ft_CategoricalDistribution as Categorical  # noqa: F401
from .optunaspaces import ft_FloatDistribution as Real  # noqa: F401
from .optunaspaces import ft_IntDistribution as Integer  # noqa: F401
