from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import MergerLLMNodeConfig
from ..identifiers import META, Identifier
from ..llm_merger import LLMMergerNode
from ..llm_merger_node_factory import LLMMergerNodeFactory
from ..validator import LLMMergerNodeValidator


class LLMMergerNodeElementSpec(BaseElementSpec):
    """Element specification for LLM Merger Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MergerLLMNodeConfig
    factory_cls = LLMMergerNodeFactory
    reads = LLMMergerNode.total_reads()
    writes = LLMMergerNode.total_writes()
    tags = META.tags
    validator_cls = LLMMergerNodeValidator
