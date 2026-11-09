from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.openai_compatible.elements.openai_compatible.config import (
    OpenAICompatibleConfig,
)
from plugins.openai_compatible.elements.openai_compatible.identifiers import (
    META,
    Identifier,
)
from plugins.openai_compatible.elements.openai_compatible.openai_compatible_factory import (
    OpenAICompatibleFactory,
)
from plugins.openai_compatible.elements.openai_compatible.validator import (
    OpenAICompatibleLLMValidator,
)


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
