from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .config import RouterDirectConditionConfig
from .identifiers import Identifier
from .router import RouterDirectCondition


class RouterDirectConditionFactory(BaseFactory[RouterDirectConditionConfig, RouterDirectCondition]):
    """Factory for RouterDirectCondition."""

    def accepts(self, cfg: RouterDirectConditionConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: RouterDirectConditionConfig, **deps) -> RouterDirectCondition:
        """
        deps delivers at least:
          • step_ctx  – mandatory identity capsule
        """
        try:
            return RouterDirectCondition()
        except Exception as exc:
            raise PluginConfigurationError(
                f"RouterDirectConditionFactory.create failed: {exc}", cfg.dict()
            ) from exc
