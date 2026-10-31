from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import OpenAICompatibleConfig
from ..identifiers import META, Identifier
from ..openai_compatible_factory import OpenAICompatibleFactory
from ..validator import OpenAICompatibleLLMValidator


class OpenAICompatibleElementSpec(BaseElementSpec):
    """
    Element specification for OpenAI-compatible LLM.

    Provides all metadata needed for UI integration and runtime configuration.
    """

    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OpenAICompatibleConfig
    factory_cls = OpenAICompatibleFactory
    tags = META.tags
    validator_cls = OpenAICompatibleLLMValidator
