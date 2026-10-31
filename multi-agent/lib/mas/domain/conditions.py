"""Portable condition outcomes and authoring metadata, independent of execution."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

type ConditionResult = bool | str | list[str] | tuple[str, ...]


class BranchType(StrEnum):
    SYMBOLIC = "symbolic"
    DIRECT = "direct"
    FLEXIBLE = "flexible"


class SymbolicBranchDef(BaseModel):
    name: str | bool | int | float
    display_name: str
    description: str = ""


class DirectBranchDef(BaseModel):
    description: str = ""


class ConditionOutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_type: BranchType
    symbolic_branches: list[SymbolicBranchDef] = Field(default_factory=list)
    direct_config: DirectBranchDef = Field(default_factory=DirectBranchDef)
    default_branch: str | None = None
    description: str = ""


def boolean_condition_schema(description: str) -> ConditionOutputSchema:
    return ConditionOutputSchema(
        branch_type=BranchType.SYMBOLIC,
        symbolic_branches=[
            SymbolicBranchDef(
                name=value, display_name=str(value), description=f"Condition is {value}"
            )
            for value in (True, False)
        ],
        description=description,
    )
