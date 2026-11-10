from typing import Literal

from lumora.elements.tools.configuration.base_config import BaseToolConfig
from plugins.web.elements.web_fetch.identifiers import Identifier


class WebFetchToolConfig(BaseToolConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
