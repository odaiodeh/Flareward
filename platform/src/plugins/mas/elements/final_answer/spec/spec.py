from typing import ClassVar

from flareward.elements.hints import HiddenHint
from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.mas.elements.final_answer.config import FinalAnswerNodeConfig
from plugins.mas.elements.final_answer.final_answer import FinalAnswerNode
from plugins.mas.elements.final_answer.final_answer_node_factory import (
    FinalAnswerNodeFactory,
)
from plugins.mas.elements.final_answer.identifiers import META, Identifier


class FinalAnswerNodeElementSpec(GraphElementSpec):
    """Element specification for Final Answer Node."""

    category: ClassVar[ResourceCategory] = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = FinalAnswerNodeConfig
    factory_cls = FinalAnswerNodeFactory
    reads = FinalAnswerNode.total_reads()
    writes = FinalAnswerNode.total_writes()
    tags = META.tags
    hints = [HiddenHint(reason="UI hidden element").model_dump(mode="json")]
