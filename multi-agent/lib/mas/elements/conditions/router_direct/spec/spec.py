from typing import ClassVar

from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import RouterDirectConditionConfig
from ..identifiers import META, Identifier
from ..router import RouterDirectCondition
from ..router_condition_factory import RouterDirectConditionFactory


class RouterDirectConditionElementSpec(BaseElementSpec):
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
