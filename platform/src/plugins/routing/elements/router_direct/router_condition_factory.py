from flareward.elements.exceptions import PluginConfigurationError
from flareward.elements.factory import BaseFactory
from plugins.routing.elements.router_direct.config import RouterDirectConditionConfig
from plugins.routing.elements.router_direct.identifiers import Identifier
from plugins.routing.elements.router_direct.router import RouterDirectCondition


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
