"""
IHyperStrategy interface, hyperoptable Parameter class.
This module defines a base class for auto-hyperoptable strategies.
"""

import logging
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from freqtrade.constants import HYPEROPT_BUILTIN_SPACES, Config
from freqtrade.exceptions import OperationalException
from freqtrade.misc import deep_merge_dicts
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from freqtrade.strategy.parameters import BaseParameter


logger = logging.getLogger(__name__)


class HyperStrategyMixin:
    """
    A helper base class which allows HyperOptAuto class to reuse implementations of buy/sell
     strategy logic.
    """

    def __init__(self, config: Config, *args, **kwargs):
        """
        Initialize hyperoptable strategy mixin.
        """
        self.config = config

        params = self.load_params_from_file()
        params = params.get("params", {})
        self._ft_params_from_file = params
        # Init/loading of parameters is done as part of ft_bot_start().

    def enumerate_parameters(
        self, category: str | None = None
    ) -> Iterator[tuple[str, BaseParameter]]:
        """
        Find all optimizable parameters and return (name, attr) iterator.
        :param category:
        :return:
        """
        if category is None:
            params = self.ft_buy_params + self.ft_sell_params + self.ft_protection_params
        else:
            params = self._ft_get_param_container(category)

        for par in params:
            yield par.name, par

    def ft_load_params_from_file(self) -> None:
        """
        Load Parameters from parameter file
        Should/must run before config values are loaded in strategy_resolver.
        """
        if self._ft_params_from_file:
            # Set parameters from Hyperopt results file
            params = self._ft_params_from_file
            self.minimal_roi = params.get("roi", getattr(self, "minimal_roi", {}))

            self.stoploss = params.get("stoploss", {}).get(
                "stoploss", getattr(self, "stoploss", -0.1)
            )
            self.max_open_trades = params.get("max_open_trades", {}).get(
                "max_open_trades", getattr(self, "max_open_trades", -1)
            )
            trailing = params.get("trailing", {})
            self.trailing_stop = trailing.get(
                "trailing_stop", getattr(self, "trailing_stop", False)
            )
            self.trailing_stop_positive = trailing.get(
                "trailing_stop_positive", getattr(self, "trailing_stop_positive", None)
            )
            self.trailing_stop_positive_offset = trailing.get(
                "trailing_stop_positive_offset", getattr(self, "trailing_stop_positive_offset", 0)
            )
            self.trailing_only_offset_is_reached = trailing.get(
                "trailing_only_offset_is_reached",
                getattr(self, "trailing_only_offset_is_reached", 0.0),
            )

    def ft_load_hyper_params(self, hyperopt: bool = False) -> None:
        """
        Load Hyperoptable parameters
        Prevalence:
        * Parameters from parameter file
        * Parameters defined in parameters objects (buy_params, sell_params, ...)
        * Parameter defaults
        """
        spaces = ["buy", "sell", "protection"]
        spaces += [
            s
            for s in self.config.get("spaces", [])
            if s not in spaces and s not in HYPEROPT_BUILTIN_SPACES
        ]

        for space in spaces:
            params = deep_merge_dicts(
                self._ft_params_from_file.get(space, {}), getattr(self, f"{space}_params", {})
            )
            self._ft_load_params(params, space, hyperopt)

    def load_params_from_file(self) -> dict:
        filename_str = getattr(self, "__file__", "")
        if not filename_str:
            return {}
        filename = Path(filename_str).with_suffix(".json")

        if filename.is_file():
            logger.info(f"Loading parameters from file {filename}")
            try:
                params = HyperoptTools.load_params(filename)
                if params.get("strategy_name") != self.__class__.__name__:
                    raise OperationalException("Invalid parameter file provided.")
                return params
            except ValueError:
                logger.warning("Invalid parameter file format.")
                return {}
        logger.info("Found no parameter file.")

        return {}

    def _ft_get_param_container(self, category: str) -> list[BaseParameter]:
        """
        Get parameter container for category/space.
        Creates the attribute if it does not exist yet.
        :param category: category - usually 'buy', 'sell', 'protection',...
        :return: list of parameters for category
        """
        container_name = f"ft_{category}_params"
        if not hasattr(self, container_name):
            setattr(self, container_name, [])
        return getattr(self, container_name)

    def _ft_load_params(self, params: dict, space: str, hyperopt: bool = False) -> None:
        """
        Set optimizable parameter values.
        :param params: Dictionary with new parameter values.
        """
        if not params:
            logger.info(f"No params for {space} found, using default values.")
        param_container: list[BaseParameter] = self._ft_get_param_container(space)

        for attr_name, attr in detect_parameters(self, space):
            attr.name = attr_name
            attr.in_space = hyperopt and HyperoptTools.has_space(self.config, space)
            if not attr.category:
                attr.category = space

            param_container.append(attr)

            if params and attr_name in params:
                if attr.load:
                    attr.value = params[attr_name]
                    logger.info(f"Strategy Parameter: {attr_name} = {attr.value}")
                else:
                    logger.warning(
                        f'Parameter "{attr_name}" exists, but is disabled. '
                        f'Default value "{attr.value}" used.'
                    )
            else:
                logger.info(f"Strategy Parameter(default): {attr_name} = {attr.value}")

    def get_no_optimize_params(self) -> dict[str, dict]:
        """
        Returns list of Parameters that are not part of the current optimize job
        """
        params: dict[str, dict] = {
            "buy": {},
            "sell": {},
            "protection": {},
        }
        for name, p in self.enumerate_parameters():
            if p.category and (not p.optimize or not p.in_space):
                params[p.category][name] = p.value
        return params


def detect_parameters(
    obj: HyperStrategyMixin | type[HyperStrategyMixin], category: str
) -> Iterator[tuple[str, BaseParameter]]:
    """
    TODO: replace with the below logic completely
    Detect all parameters for 'category' for "obj"
    :param obj: Strategy object or class
    :param category: category - usually `'buy', 'sell', 'protection',...
    """
    for attr_name in dir(obj):
        if not attr_name.startswith("__"):  # Ignore internals, not strictly necessary.
            attr = getattr(obj, attr_name)
            if issubclass(attr.__class__, BaseParameter):
                if (
                    attr_name.startswith(category + "_")
                    and attr.category is not None
                    and attr.category != category
                ):
                    raise OperationalException(
                        f"Inconclusive parameter name {attr_name}, category: {attr.category}."
                    )

                if category == attr.category or (
                    attr_name.startswith(category + "_") and attr.category is None
                ):
                    yield attr_name, attr


def detect_all_parameters(
    obj: HyperStrategyMixin | type[HyperStrategyMixin],
) -> dict[str, list[BaseParameter]]:
    """
    Detect all hyperoptable parameters for this object.
    :param obj: Strategy object or class
    """
    auto_categories = ["buy", "sell", "protection"]
    result: dict[str, list[BaseParameter]] = defaultdict(list)
    for attr_name in dir(obj):
        if attr_name.startswith("__"):  # Ignore internals
            continue
        attr = getattr(obj, attr_name)
        if not issubclass(attr.__class__, BaseParameter):
            continue
        category = attr.category
        if attr.category is None:
            # Category auto detection
            for category in auto_categories:
                if category == attr.category or (
                    attr_name.startswith(category + "_") and attr.category is None
                ):
                    attr.category = category
        if attr.category is None or (
            attr_name.startswith(category + "_")
            and attr.category is not None
            and attr.category != category
        ):
            raise OperationalException(
                f"Inconclusive parameter name {attr_name}, space: {attr.category}."
            )

        result[attr.category].append(attr)
    return result
