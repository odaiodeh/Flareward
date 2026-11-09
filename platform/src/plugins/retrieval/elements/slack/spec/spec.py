from flareward.elements.retrieval.card_builder import RetrieverCardBuilder
from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory

from ..config import SlackRetrieverConfig
from ..identifiers import META, Identifier
from ..slack_retriever_factory import SlackRetrieverFactory


class SlackRetrieverElementSpec(BaseElementSpec):
    """Element specification for Slack Retriever."""

    category = ResourceCategory.RETRIEVER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = SlackRetrieverConfig
    factory_cls = SlackRetrieverFactory
    tags = META.tags
    card_builder_cls = RetrieverCardBuilder
