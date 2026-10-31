from typing import Literal

from mas.application.elements.node_config import NodeBaseConfig
from mas.core.field_hints import CardContext, CardHint
from mas.core.ref.models import LLMRef
from pydantic import Field

from .identifiers import Identifier


class MockAgentNodeConfig(NodeBaseConfig):
    """
    Allows overriding only the LLM key for the mock agent node.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: LLMRef | None = Field(
        None,
        description="LLM key to use for the mock agent",
        title="LLM",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    echo_message: str | None = Field(
        None,
        description="Optional fixed message to return",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
