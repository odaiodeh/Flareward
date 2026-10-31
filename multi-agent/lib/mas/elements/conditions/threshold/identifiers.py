from dataclasses import dataclass
from enum import StrEnum


class Identifier(StrEnum):
    """Machine-readable key for the Threshold Condition."""

    TYPE = "threshold"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: list[str]


META = Meta(
    name="Threshold Condition",
    description="Triggers when the state's value crosses the numeric threshold",
    tags=["condition", "threshold", "numeric"],
)
