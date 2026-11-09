from typing import ClassVar

from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.routing.elements.router_direct.config import RouterDirectConditionConfig
from plugins.routing.elements.router_direct.identifiers import META, Identifier
from plugins.routing.elements.router_direct.router import RouterDirectCondition
from plugins.routing.elements.router_direct.router_condition_factory import (
    RouterDirectConditionFactory,
)


class RouterDirectConditionElementSpec(GraphElementSpec):
    """Element specification for Router Direct Condition."""

    category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = RouterDirectConditionConfig
    factory_cls = RouterDirectConditionFactory
    reads = RouterDirectCondition.READS
    tags = META.tags
    output_schema = RouterDirectCondition.get_output_schema()
