from typing import Literal

from mas.application.elements.node_config import NodeBaseConfig

from .identifiers import Identifier


class UserQuestionNodeConfig(NodeBaseConfig):
    """
    Logs or passes through user input without modification.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
