from typing import ClassVar

from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory
from mas.core.field_hints import HiddenHint

from ..config import FinalAnswerNodeConfig
from ..final_answer import FinalAnswerNode
from ..final_answer_node_factory import FinalAnswerNodeFactory
from ..identifiers import META, Identifier


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
