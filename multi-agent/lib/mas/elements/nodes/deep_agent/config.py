from typing import Any, Literal

from pydantic import Field, model_validator

from mas.application.elements.node_config import NodeBaseConfig, retired_sandbox_configuration
from mas.core.field_hints import (
    ApiHint,
    CardContext,
    CardHint,
    HiddenHint,
    HintType,
    SelectionType,
    combine_hints,
)
from mas.core.hitl.models import HITLMode
from mas.core.ref.models import LLMRef, ProviderRef, RetrieverRef, ToolRef

from .identifiers import Identifier


class DeepAgentNodeConfig(NodeBaseConfig):
    """
    Deep Agent node powered by LangChain Deep Agents.

    Delegates execution to a compiled Deep Agent graph that provides
    built-in planning (todos), context management, and a general-purpose
    subagent for automatic task delegation.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    llm: LLMRef = Field(
        description="LLM Ref UID to use as the Deep Agent's model",
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
        description="Retriever for context augmentation (optional)",
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
        description="System prompt for the Deep Agent",
    )

    # --- Backend / Environment ---

    cwd: str | None = Field(
        default=None,
        description="Working directory override (defaults to shared_storage/{session}/{node})",
        json_schema_extra=HiddenHint(reason="Advanced: override working directory").to_hints(),
    )

    env_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables for the deep agent session",
        json_schema_extra=HiddenHint(reason="Advanced: custom environment variables").to_hints(),
    )

    hitl_mode: HITLMode = Field(
        default=HITLMode.SKIP,
        description="HITL approval mode: ask (always), skip (never), dynamic (runtime flag)",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_retired_sandbox(cls, value: Any) -> Any:
        return retired_sandbox_configuration(value)
