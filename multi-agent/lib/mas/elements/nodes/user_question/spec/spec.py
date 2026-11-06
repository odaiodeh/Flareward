from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory
from mas.core.field_hints import HiddenHint

from ..config import UserQuestionNodeConfig
from ..identifiers import META, Identifier
from ..user_question import UserQuestionNode
from ..user_question_node_factory import UserQuestionNodeFactory


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
