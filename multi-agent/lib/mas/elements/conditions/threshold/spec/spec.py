from typing import ClassVar

from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import ThresholdConditionConfig
from ..identifiers import META, Identifier
from ..threshold import ThresholdCondition
from ..threshold_factory import ThresholdConditionFactory


class ThresholdConditionElementSpec(BaseElementSpec):
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
