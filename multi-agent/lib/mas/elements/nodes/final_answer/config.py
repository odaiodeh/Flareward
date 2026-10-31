from typing import Literal

from mas.application.elements.node_config import NodeBaseConfig

from .identifiers import Identifier


class FinalAnswerNodeConfig(NodeBaseConfig):
    """
    Emits the final aggregated answer without overrides.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
