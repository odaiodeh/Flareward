from typing import ClassVar

from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.routing.elements.threshold.config import ThresholdConditionConfig
from plugins.routing.elements.threshold.identifiers import META, Identifier
from plugins.routing.elements.threshold.threshold import ThresholdCondition
from plugins.routing.elements.threshold.threshold_factory import ThresholdConditionFactory


class ThresholdConditionElementSpec(GraphElementSpec):
    """Element specification for Threshold Condition."""

    category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = ThresholdConditionConfig
    factory_cls = ThresholdConditionFactory
    reads = ThresholdCondition.read_channels()
    tags = META.tags
    output_schema = ThresholdCondition.get_output_schema()
