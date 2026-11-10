"""
Template instantiation module.

Handles merging user input into templates and materializing resources.
"""

# Re-export error models from central location
from lumora.services.templates.errors import (
    MaterializationError,
    MaterializationErrorType,
    MaterializationFieldError,
    MergeError,
    MergeErrorType,
    MergeFieldError,
)
from lumora.services.templates.instantiation.instantiator import TemplateInstantiator
from lumora.services.templates.instantiation.materializer import ResourceMaterializer
from lumora.services.templates.instantiation.models import (
    CollectedResource,
    InstantiationResult,
    MaterializationResult,
)

__all__ = [
    # Models
    "CollectedResource",
    "InstantiationResult",
    "MaterializationResult",
    # Classes
    "TemplateInstantiator",
    "ResourceMaterializer",
    # Error models (re-exported for convenience)
    "MergeError",
    "MergeErrorType",
    "MergeFieldError",
    "MaterializationError",
    "MaterializationErrorType",
    "MaterializationFieldError",
]
