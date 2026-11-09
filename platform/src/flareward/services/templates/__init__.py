"""
Template System Module

Provides public blueprint templates with placeholder support.
Allows users to instantiate templates by filling in missing fields,
then materializes resources and blueprints to their account.

Architecture:
- models/: Template data models (Template, PlaceholderMeta)
- repository/: Template persistence
- schema/: Placeholder analysis and dynamic schema generation
- instantiation/: Merge user input into BlueprintDraft
- errors.py: Consolidated error models
- service.py: Public facade (TemplateService)

Key insight: Templates store valid BlueprintDrafts. Placeholder fields
contain default values that pass validation. The PlaceholderMeta just
points to which fields should be replaced with user input.

Usage:
    from flareward.services.templates import TemplateService

    # Get input schema for a template
    schema = template_service.get_input_schema(template_id)

    # Instantiate with user input
    result = template_service.instantiate(template_id, user_input)
    result.blueprint       # The merged BlueprintDraft
    result.filled_fields   # List of fields that were filled

    # Or materialize to user's account (saves blueprint + resources)
    result = template_service.materialize(
        template_id=template_id,
        user_id=user_id,
        user_input=user_input,
    )
"""

from flareward.services.templates.errors import (
    InstantiationError,
    # Materialization errors
    MaterializationError,
    MaterializationErrorType,
    MaterializationFieldError,
    # Merge errors
    MergeError,
    MergeErrorType,
    MergeFieldError,
    # Service errors
    TemplateNotFoundError,
    TemplateSaveError,
)
from flareward.services.templates.instantiation import (
    InstantiationResult,
    MaterializationResult,
    ResourceMaterializer,
    TemplateInstantiator,
)
from flareward.services.templates.models.template import (
    CategoryPlaceholders,
    PlaceholderMeta,
    PlaceholderPointer,
    ResourcePlaceholders,
    Template,
    TemplateMetadata,
    TemplateSummary,
)
from flareward.services.templates.service import MaterializeResult, TemplateService

__all__ = [
    # Main service
    "TemplateService",
    "MaterializeResult",
    # Template models
    "Template",
    "TemplateSummary",
    "PlaceholderMeta",
    "PlaceholderPointer",
    "ResourcePlaceholders",
    "CategoryPlaceholders",
    "TemplateMetadata",
    # Instantiation
    "TemplateInstantiator",
    "InstantiationResult",
    "ResourceMaterializer",
    "MaterializationResult",
    # Error models
    "MergeError",
    "MergeErrorType",
    "MergeFieldError",
    "MaterializationError",
    "MaterializationErrorType",
    "MaterializationFieldError",
    "TemplateNotFoundError",
    "TemplateSaveError",
    "InstantiationError",
]
