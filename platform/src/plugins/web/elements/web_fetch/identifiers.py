from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Web Fetch tool."""

    TYPE = "web_fetch"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Web Fetch",
    description="Fetch a web page and return its content as clean markdown",
    tags=["tool", "web", "fetch", "http", "url"],
)
