from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Mock LLM."""

    TYPE = "mock"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Mock LLM",
    description="Returns a constant or echo—for testing",
    tags=["llm", "mock", "test", "echo"],
)
