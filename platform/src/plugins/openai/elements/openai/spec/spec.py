from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.openai.elements.openai.config import OpenAIConfig
from plugins.openai.elements.openai.identifiers import META, Identifier
from plugins.openai.elements.openai.openai_factory import OpenAIFactory
from plugins.openai.elements.openai.validator import OpenAILLMValidator


class OpenAIElementSpec(BaseElementSpec):
    """
    Element specification for OpenAI LLM.

    Provides all metadata needed for UI integration and runtime configuration.
    """

    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OpenAIConfig
    factory_cls = OpenAIFactory
    tags = META.tags
    validator_cls = OpenAILLMValidator
