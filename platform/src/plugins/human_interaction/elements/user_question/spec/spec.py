from lumora.elements.hints import HiddenHint
from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.human_interaction.elements.user_question.config import UserQuestionNodeConfig
from plugins.human_interaction.elements.user_question.identifiers import META, Identifier
from plugins.human_interaction.elements.user_question.user_question import (
    UserQuestionNode,
)
from plugins.human_interaction.elements.user_question.user_question_node_factory import (
    UserQuestionNodeFactory,
)


class UserQuestionNodeElementSpec(GraphElementSpec):
    """Element specification for User Question Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = UserQuestionNodeConfig
    factory_cls = UserQuestionNodeFactory
    reads = UserQuestionNode.total_reads()
    writes = UserQuestionNode.total_writes()
    tags = META.tags
    hints = [HiddenHint(reason="UI hidden element").model_dump(mode="json")]
