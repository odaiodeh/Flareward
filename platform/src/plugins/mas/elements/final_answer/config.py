from typing import Literal

from lumora.elements.node_config import NodeBaseConfig
from plugins.mas.elements.final_answer.identifiers import Identifier


class FinalAnswerNodeConfig(NodeBaseConfig):
    """
    Emits the final aggregated answer without overrides.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
