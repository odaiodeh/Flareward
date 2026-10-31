from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.retrievers.common.card_builder import RetrieverCardBuilder

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
