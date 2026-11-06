from typing import ClassVar

from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory

from ..config import RouterBooleanConditionConfig
from ..identifiers import META, Identifier
from ..router import RouterBooleanCondition
from ..router_condition_factory import RouterBooleanConditionFactory


class RouterBooleanConditionElementSpec(GraphElementSpec):
    """Element specification for Router Boolean Condition."""

    category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = RouterBooleanConditionConfig
    factory_cls = RouterBooleanConditionFactory
    tags = META.tags
    reads = RouterBooleanCondition.READS
    output_schema = RouterBooleanCondition.get_output_schema()
