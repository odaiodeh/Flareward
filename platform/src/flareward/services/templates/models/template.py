"""
Template models for public blueprint templates.

Templates store valid BlueprintDrafts with placeholder metadata
indicating which fields require user input before instantiation.

Key insight: The draft is always valid! Placeholder fields contain
default/dummy values (e.g., "PLACEHOLDER_API_KEY") that pass validation.
The PlaceholderMeta just points to which fields need user input.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from flareward.programs.templates.models.blueprint import BlueprintDraft
from flareward.resources.domain.categories import ResourceCategory


class PlaceholderPointer(BaseModel):
    """
    Points to a specific field that requires user input.

    Minimal structure - just identifies the field location.
    Type information and validation rules are extracted from
    the element's config_schema at runtime via PlaceholderAnalyzer.
    """

    field_path: str = Field(
        ...,
        description="Dot-notation path to the placeholder field (e.g., 'api_key', 'flareward.bootstrap.settings.model_name')",
    )
    required: bool = Field(
        default=True, description="Whether this field is required for instantiation"
    )
    label: Optional[str] = Field(
        default=None, description="Human-readable label for the field (defaults to field name)"
    )
    hint: Optional[str] = Field(default=None, description="Additional hint text for the user")

    model_config = {"extra": "forbid"}


class ResourcePlaceholders(BaseModel):
    """
    Placeholder metadata for a single resource.

    Links resource ID to its placeholder fields.
    """

    rid: str = Field(..., description="Resource ID within the template")
    placeholders: List[PlaceholderPointer] = Field(
        default_factory=list, description="List of placeholder fields for this resource"
    )

    model_config = {"extra": "forbid"}


class CategoryPlaceholders(BaseModel):
    """
    Placeholder metadata grouped by category.
    """

    category: ResourceCategory
    resources: List[ResourcePlaceholders] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class PlaceholderMeta(BaseModel):
    """
    Complete placeholder metadata for a template.

    Organized by category > resource > field for easy traversal.
    """

    categories: List[CategoryPlaceholders] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    def iter_all_placeholders(self):
        """
        Iterate over all placeholders.

        Yields (category, rid, placeholder) tuples.
        """
        for cat in self.categories:
            for res in cat.resources:
                for placeholder in res.placeholders:
                    yield cat.category, res.rid, placeholder

    def placeholder_count(self) -> int:
        """Return total count of placeholder fields."""
        return sum(1 for _ in self.iter_all_placeholders())


class TemplateMetadata(BaseModel):
    """
    Template metadata for catalog and discovery.
    """

    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    is_public: bool = True
    preview_image_url: Optional[str] = None
    category: Optional[str] = Field(
        default=None,
        description="Template category for catalog organization (e.g., 'Chat', 'RAG', 'Agents')",
    )
    output_capabilities: List[str] = Field(
        default_factory=list,
        description="List of output capabilities (e.g., 'streaming', 'json', 'markdown')",
    )

    model_config = {"extra": "forbid"}


class Template(BaseModel):
    """
    A public blueprint template with placeholder support.

    Combines:
    - BlueprintDraft: A valid blueprint (placeholder fields have default values)
    - PlaceholderMeta: Metadata about which fields need user input
    - TemplateMetadata: Catalog metadata (author, tags, etc.)

    The draft is always valid! Placeholder fields contain default/dummy values
    that pass Pydantic validation. The PlaceholderMeta just points to which
    fields should be replaced with user input.
    """

    template_id: str = Field(..., description="Unique template identifier")
    draft: BlueprintDraft = Field(
        ..., description="The template blueprint (valid, with placeholder defaults)"
    )
    placeholders: PlaceholderMeta = Field(
        default_factory=PlaceholderMeta, description="Metadata about placeholder fields"
    )
    metadata: TemplateMetadata = Field(
        default_factory=TemplateMetadata, description="Template catalog metadata"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}

    @property
    def name(self) -> str:
        """Template name (from draft)."""
        return self.draft.name

    @property
    def description(self) -> str:
        """Template description (from draft)."""
        return self.draft.description


class TemplateSummary(BaseModel):
    """
    Lightweight template info for catalog display.

    Read-only projection of Template for API responses.
    """

    template_id: str
    name: str
    description: str
    placeholder_count: int
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    output_capabilities: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    is_public: bool = True
    created_at: datetime

    model_config = {"frozen": True, "extra": "forbid"}

    @classmethod
    def from_template(cls, template: Template) -> "TemplateSummary":
        """Create summary from full template."""
        return cls(
            template_id=template.template_id,
            name=template.name,
            description=template.description,
            placeholder_count=template.placeholders.placeholder_count(),
            category=template.metadata.category,
            tags=template.metadata.tags,
            version=template.metadata.version,
            output_capabilities=template.metadata.output_capabilities,
            author=template.metadata.author,
            is_public=template.metadata.is_public,
            created_at=template.created_at,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Service Result Models
# ─────────────────────────────────────────────────────────────────────────────
class InputValidationResult(BaseModel):
    """Result of input validation."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class MaterializeResult(BaseModel):
    """Result of template materialization."""

    blueprint_id: str
    template_id: str
    fields_filled: int
    name: str
    resources_created: int
    resource_ids: List[str] = Field(default_factory=list)

    model_config = {"frozen": True}
