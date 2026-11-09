from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Custom Agent node."""

    TYPE = "custom_agent_node"


@dataclass(frozen=True)
class Meta:
    """Human-readable metadata about the element."""

    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Custom Agent Node",
    description="Agent node with LLM, retriever, tools, and prompt overrides",
    tags=[
        "agent",
        "node",
        "custom",
        "llm",
        "retriever",
        "tools",
    ],
)
