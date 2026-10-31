from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import WebFetchToolConfig
from ..identifiers import META, Identifier
from ..web_fetch_factory import WebFetchToolFactory


class WebFetchToolElementSpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = WebFetchToolConfig
    factory_cls = WebFetchToolFactory
    tags = META.tags
