from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Slack Retriever."""

    TYPE = "slack"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Slack Retriever",
    description="Fetches recent messages matching a query from Slack",
    tags=["retriever", "slack", "search", "query", "information retrieval"],
)
