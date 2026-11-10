"""
Data models for instantiation and materialization.

Separates data structures from business logic (SOLID: SRP).
"""

from typing import Dict, List, NamedTuple

from pydantic import BaseModel, Field

from lumora.programs.templates.models.blueprint import BlueprintDraft, BlueprintResource
from lumora.resources.domain.categories import ResourceCategory


# ─────────────────────────────────────────────────────────────────────────────
#  Internal Data Structures
# ─────────────────────────────────────────────────────────────────────────────
class CollectedResource(NamedTuple):
    """A collected inline resource ready for processing."""

    template_rid: str
    final_rid: str
    category: ResourceCategory
    bp_resource: BlueprintResource


# ─────────────────────────────────────────────────────────────────────────────
#  Public Result Models
# ─────────────────────────────────────────────────────────────────────────────
class InstantiationResult(BaseModel):
    """Result of template instantiation."""

    blueprint: BlueprintDraft
    template_id: str
    filled_fields: List[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @property
    def field_count(self) -> int:
        """Number of fields that were filled."""
        return len(self.filled_fields)


class MaterializationResult(BaseModel):
    """Result of materializing a blueprint."""

    blueprint_draft: BlueprintDraft
    resource_ids: List[str] = Field(default_factory=list)
    id_mapping: Dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}
