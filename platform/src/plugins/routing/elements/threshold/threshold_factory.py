from flareward.elements.factory import BaseFactory
from plugins.routing.elements.threshold.config import ThresholdConditionConfig
from plugins.routing.elements.threshold.identifiers import Identifier
from plugins.routing.elements.threshold.threshold import ThresholdCondition


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
