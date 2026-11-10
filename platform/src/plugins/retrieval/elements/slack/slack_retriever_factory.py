from typing import Any

from lumora.elements.construction.context import ElementBuildContext
from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory

from .config import SlackRetrieverConfig
from .identifiers import Identifier
from .slack_retriever import SlackRetriever


class SlackRetrieverFactory(BaseFactory[SlackRetrieverConfig, SlackRetriever]):
    def accepts(self, cfg: SlackRetrieverConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: SlackRetrieverConfig, **kwargs: Any) -> SlackRetriever:
        deps: ElementBuildContext | None = kwargs.get("deps")
        try:
            return SlackRetriever(
                api_url=cfg.api_url,
                top_k_results=cfg.top_k_results,
                threshold=cfg.threshold,
                identity=deps.execution_ctx if deps else None,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"SlackRetrieverFactory.create() failed: {e}", cfg.dict()
            ) from e
