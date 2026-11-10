from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory
from plugins.routing.elements.router_boolean.config import RouterBooleanConditionConfig
from plugins.routing.elements.router_boolean.identifiers import Identifier
from plugins.routing.elements.router_boolean.router import RouterBooleanCondition


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
