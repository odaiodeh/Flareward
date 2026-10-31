from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class NodePosition(StrEnum):
    START = "start"
    END = "end"
    ANY = "any"


class RequiredNodeFixType(StrEnum):
    ADD_REQUIRED_START = "add_required_start"
    ADD_REQUIRED_END = "add_required_end"
    ADD_REQUIRED_ANYWHERE = "add_required_anywhere"


class RequiredNodeIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_type: NodePosition
    expected: str
    actual: str | None


class RequiredNodesDetails(BaseModel):
    model_config = ConfigDict(frozen=True)

    required_node_issues: list[RequiredNodeIssue]
    missing_start_nodes: set[str]
    missing_end_nodes: set[str]
