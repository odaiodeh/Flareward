from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import OpenAIConfig
from ..identifiers import META, Identifier
from ..openai_factory import OpenAIFactory
from ..validator import OpenAILLMValidator


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
