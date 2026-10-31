from mas.application.elements.factory import BaseFactory

from .config import ThresholdConditionConfig
from .identifiers import Identifier
from .threshold import ThresholdCondition


class ThresholdConditionFactory(BaseFactory[ThresholdConditionConfig, ThresholdCondition]):
    """
    Factory that builds a ThresholdCondition from its config.
    """

    def accepts(self, cfg: ThresholdConditionConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: ThresholdConditionConfig, **deps) -> ThresholdCondition:
        return ThresholdCondition(
            input_path=cfg.input_path, threshold=cfg.threshold, comparison=cfg.operator
        )
