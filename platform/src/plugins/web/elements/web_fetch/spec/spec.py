from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.web.elements.web_fetch.config import WebFetchToolConfig
from plugins.web.elements.web_fetch.identifiers import META, Identifier
from plugins.web.elements.web_fetch.web_fetch_factory import WebFetchToolFactory


class WebFetchToolElementSpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = WebFetchToolConfig
    factory_cls = WebFetchToolFactory
    tags = META.tags
