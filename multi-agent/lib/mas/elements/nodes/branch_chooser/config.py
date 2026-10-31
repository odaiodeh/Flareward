from typing import Literal

from pydantic import Field

from mas.application.elements.node_config import NodeBaseConfig
from mas.core.field_hints import CardContext, CardHint

from .identifiers import Identifier


class BranchChooserNodeConfig(NodeBaseConfig):
    """
    Configuration for the branch chooser node that selects the first target branch.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    default_branch: str | None = Field(
        None,
        description="Default branch name to use if no target branches are available",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
