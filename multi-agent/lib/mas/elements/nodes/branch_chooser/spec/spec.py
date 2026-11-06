from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory

from ..branch_chooser import BranchChooserNode
from ..branch_chooser_node_factory import BranchChooserNodeFactory
from ..config import BranchChooserNodeConfig
from ..identifiers import META, Identifier


class BranchChooserNodeElementSpec(GraphElementSpec):
    """Element specification for Branch Chooser Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = BranchChooserNodeConfig
    factory_cls = BranchChooserNodeFactory
    reads = BranchChooserNode.total_reads()
    writes = BranchChooserNode.total_writes()
    tags = META.tags
