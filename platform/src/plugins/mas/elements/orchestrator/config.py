from typing import Literal

from pydantic import Field

from lumora.elements.hints import (
    ApiHint,
    CardContext,
    CardHint,
    HintType,
    SelectionType,
    combine_hints,
)
from lumora.elements.node_config import NodeBaseConfig
from lumora.resources.domain.references import LLMRef, ToolRef
from plugins.mas.elements.orchestrator.identifiers import Identifier


class OrchestratorNodeConfig(NodeBaseConfig):
    """
    Orchestrator node configuration.

    Orchestrator nodes coordinate work execution by:
    - Creating work plans from incoming tasks
    - Delegating work items to adjacent nodes
    - Monitoring responses and updating plan status
    - Synthesizing results when complete
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: LLMRef = Field(
        description="LLM Ref UID to use for planning and coordination",
        title="LLM",
        json_schema_extra=combine_hints(
            ApiHint(
                endpoint="/resources/resource.validate",
                method="POST",
                hint_type=HintType.VALIDATE,
                selection_type=SelectionType.AUTOMATIC,
                dependencies={"llm": "resourceId"},
                field_mapping="is_valid",
            ),
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]),
        ),
    )
    tools: list[ToolRef] | None = Field(
        default_factory=list,
        description="Domain-specific tools (orchestration tools added automatically)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    system_message: str = Field(
        "",
        description=(
            "Domain specialization message (e.g., 'I specialize in document analysis and "
            "Slack integration'). This is separate from orchestrator behavior which is built-in."
        ),
    )
    max_rounds: int = Field(
        100, description="Maximum planning/execution rounds per orchestration cycle"
    )
