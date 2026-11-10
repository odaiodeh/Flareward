"""Template models package."""

from lumora.services.templates.models.template import (
    CategoryPlaceholders,
    InputValidationResult,
    MaterializeResult,
    PlaceholderMeta,
    PlaceholderPointer,
    ResourcePlaceholders,
    Template,
    TemplateMetadata,
    TemplateSummary,
)

__all__ = [
    # Template core models
    "Template",
    "TemplateSummary",
    "PlaceholderMeta",
    "PlaceholderPointer",
    "ResourcePlaceholders",
    "CategoryPlaceholders",
    "TemplateMetadata",
    # Result models
    "InputValidationResult",
    "MaterializeResult",
]
