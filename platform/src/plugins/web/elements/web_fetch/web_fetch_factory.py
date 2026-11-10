from typing import Any

from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory
from plugins.web.elements.web_fetch.config import WebFetchToolConfig
from plugins.web.elements.web_fetch.identifiers import Identifier
from plugins.web.elements.web_fetch.web_fetch import WebFetchTool


class WebFetchToolFactory(BaseFactory[WebFetchToolConfig, WebFetchTool]):
    def accepts(self, cfg: WebFetchToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: WebFetchToolConfig, **kwargs: Any) -> WebFetchTool:
        try:
            return WebFetchTool()
        except Exception as e:
            raise PluginConfigurationError(
                f"WebFetchToolFactory.create() failed: {e}",
                cfg.dict(),
            ) from e
