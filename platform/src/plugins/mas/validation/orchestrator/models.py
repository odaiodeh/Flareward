"""
Orchestrator validation models.

Domain models for orchestrator-specific validation issues and results.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from plugins.mas.elements.orchestrator.identifiers import (
    Identifier as OrchestratorIdentifier,
)
from plugins.routing.elements.router_direct.identifiers import (
    Identifier as RouterDirectIdentifier,
)


class OrchestratorIssueType(StrEnum):
    """
    Types of issues specific to orchestrator nodes.

    Each issue type represents a violation of orchestrator delegation patterns.
    """

    INVALID_DELEGATION_EDGE = "invalid_delegation_edge"
    MISSING_RETURN_PATH = "missing_return_path"
    MISSING_FINALIZE = "missing_finalize"
    INVALID_CONDITION_TYPE = "invalid_condition_type"


class OrchestratorIssue(BaseModel):
    """
    Represents a validation issue specific to orchestrator nodes.

    Immutable model that captures the type of issue, affected nodes,
    and descriptive information for debugging and reporting.
    """

    issue_type: OrchestratorIssueType = Field(
        ..., description="Type of orchestrator validation issue"
    )

    orchestrator_uid: str = Field(..., description="UID of the orchestrator node with the issue")

    related_node_uid: str | None = Field(
        default=None, description="UID of related node (e.g., delegated worker), if applicable"
    )

    description: str = Field(..., description="Human-readable description of the issue")

    class Config:
        frozen = True


class NodeTypeConfig(BaseModel):
    """
    Configuration for node type identification.

    Generic and reusable: not specific to orchestrators.
    Uses imported type constants from element specs to avoid hardcoding.
    """

    node_type: str = Field(
        default=OrchestratorIdentifier.TYPE,
        description=(
            "Type key for the node to validate (e.g., orchestrator_node, custom_agent_node)"
        ),
    )

    required_condition_type: str = Field(
        default=RouterDirectIdentifier.TYPE,
        description="Required condition type for nodes with branches (e.g., router_direct)",
    )

    class Config:
        frozen = True
