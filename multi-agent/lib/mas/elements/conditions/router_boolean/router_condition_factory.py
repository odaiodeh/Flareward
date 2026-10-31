from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .config import RouterBooleanConditionConfig
from .identifiers import Identifier
from .router import RouterBooleanCondition


class RouterBooleanConditionFactory(
    BaseFactory[RouterBooleanConditionConfig, RouterBooleanCondition]
):
    """Factory for RouterBooleanCondition."""

    def accepts(self, cfg: RouterBooleanConditionConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: RouterBooleanConditionConfig, **deps) -> RouterBooleanCondition:
        """
        deps delivers at least:
          • step_ctx  – mandatory identity capsule
        """
        try:
            return RouterBooleanCondition(boolean_value=cfg.boolean_value)
        except Exception as exc:
            raise PluginConfigurationError(
                f"RouterBooleanConditionFactory.create failed: {exc}", cfg.dict()
            ) from exc
