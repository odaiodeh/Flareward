from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.gemini.elements.google_genai.config import GoogleGenAIConfig
from plugins.gemini.elements.google_genai.google_genai_factory import GoogleGenAIFactory
from plugins.gemini.elements.google_genai.identifiers import META, Identifier
from plugins.gemini.elements.google_genai.validator import GoogleGenAIValidator


class GoogleGenAIElementSpec(BaseElementSpec):
    """
    Element specification for Google Generative AI (Gemini) LLM.

    Provides all metadata needed for UI integration and runtime configuration.
    """

    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = GoogleGenAIConfig
    factory_cls = GoogleGenAIFactory
    tags = META.tags
    validator_cls = GoogleGenAIValidator
