from typing import ClassVar

from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import DocsRagRetrieverConfig
from ..docs_rag_retriever_factory import DocsRagRetrieverFactory
from ..identifiers import META, Identifier
from ..validator import DocsRagRetrieverValidator


class DocsRagRetrieverElementSpec(BaseElementSpec):
    """
    Element specification for Docs RAG Retriever.

    Retrieves document passages via RAG vector database.
    """

    category: ClassVar[ResourceCategory] = ResourceCategory.RETRIEVER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = DocsRagRetrieverConfig
    factory_cls = DocsRagRetrieverFactory
    tags = META.tags
    validator_cls = DocsRagRetrieverValidator
