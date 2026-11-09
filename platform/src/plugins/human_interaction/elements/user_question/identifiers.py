from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the User Question node."""

    TYPE = "user_question_node"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="User Question Node",
    description="Captures the user's question and makes it available to the agent graph",
    tags=["node", "input", "user", "question"],
)
