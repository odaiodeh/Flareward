from typing import Literal

from flareward.elements.condition_config import BaseConditionConfig
from plugins.routing.elements.router_direct.identifiers import Identifier


class RouterDirectConditionConfig(BaseConditionConfig):
    """
    Configuration for IEM-based router condition.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
