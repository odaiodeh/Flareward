from typing import Literal

from lumora.elements.node_config import NodeBaseConfig
from plugins.human_interaction.elements.user_question.identifiers import Identifier


class UserQuestionNodeConfig(NodeBaseConfig):
    """
    Logs or passes through user input without modification.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
