from typing import Literal

from mas.application.elements.condition_config import BaseConditionConfig

from .identifiers import Identifier


class RouterDirectConditionConfig(BaseConditionConfig):
    """
    Configuration for IEM-based router condition.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
