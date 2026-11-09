from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.routing.elements.branch_chooser.branch_chooser import BranchChooserNode
from plugins.routing.elements.branch_chooser.branch_chooser_node_factory import (
    BranchChooserNodeFactory,
)
from plugins.routing.elements.branch_chooser.config import BranchChooserNodeConfig
from plugins.routing.elements.branch_chooser.identifiers import META, Identifier


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
