from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.testing.elements.mock.config import MockLLMConfig
from plugins.testing.elements.mock.identifiers import META, Identifier
from plugins.testing.elements.mock.mock_factory import MockLLMFactory


class MockLLMElementSpec(BaseElementSpec):
    """Element specification for Mock LLM - testing and development."""

    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MockLLMConfig
    factory_cls = MockLLMFactory  # Factory not defined for mock LLM
    tags = META.tags
