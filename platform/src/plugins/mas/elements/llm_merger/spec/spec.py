from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.mas.elements.llm_merger.config import MergerLLMNodeConfig
from plugins.mas.elements.llm_merger.identifiers import META, Identifier
from plugins.mas.elements.llm_merger.llm_merger import LLMMergerNode
from plugins.mas.elements.llm_merger.llm_merger_node_factory import LLMMergerNodeFactory
from plugins.mas.elements.llm_merger.validator import LLMMergerNodeValidator


class LLMMergerNodeElementSpec(GraphElementSpec):
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
