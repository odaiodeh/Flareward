from typing import ClassVar

from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.routing.elements.router_boolean.config import RouterBooleanConditionConfig
from plugins.routing.elements.router_boolean.identifiers import META, Identifier
from plugins.routing.elements.router_boolean.router import RouterBooleanCondition
from plugins.routing.elements.router_boolean.router_condition_factory import (
    RouterBooleanConditionFactory,
)


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
