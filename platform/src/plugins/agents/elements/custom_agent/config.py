from typing import Literal

from pydantic import Field

from lumora.elements.agents.constants import StrategyType
from lumora.elements.hints import (
    ApiHint,
    CardContext,
    CardHint,
    HintType,
    SelectionType,
    combine_hints,
)
from lumora.elements.node_config import NodeBaseConfig
from lumora.resources.domain.references import LLMRef, ProviderRef, RetrieverRef, ToolRef
from lumora.services.interactions.tools.models import HITLMode
from plugins.agents.elements.custom_agent.identifiers import Identifier


class CustomAgentNodeConfig(NodeBaseConfig):
    """
    Custom agent node with full override capabilities.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: LLMRef = Field(
        description="LLM Ref UID to use",
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
    retriever: RetrieverRef | None = Field(
        None,
        description="Retriever key to use",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    tools: list[ToolRef] | None = Field(
        default_factory=list,
        description="List of tool keys",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    providers: list[ProviderRef] | None = Field(
        default_factory=list,
        description="List of MCP Provider Refs",
        title="MCP Servers",
        json_schema_extra=combine_hints(
            ApiHint(
                endpoint="/resources/resources.validate",
                method="POST",
                hint_type=HintType.VALIDATE,
                selection_type=SelectionType.AUTOMATIC,
                dependencies={"providers": "resourceIds"},
                field_mapping="is_valid",
            ),
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]),
        ),
    )
    system_message: str = Field(
        "",
        description="Custom system prompt",
    )
    strategy_type: str = Field(default=StrategyType.REACT.value, description="Agent strategy type")
    max_rounds: int | None = Field(
        default=100, description="Maximum number of agent execution rounds"
    )
    hitl_mode: HITLMode = Field(
        default=HITLMode.SKIP,
        description="HITL approval mode: ask (always), skip (never), dynamic (runtime flag)",
    )
