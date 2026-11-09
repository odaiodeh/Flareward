"""
Template error models.

Consolidated error definitions for the templates module.
All template-related errors and error types are defined here.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
#  Merge Errors (Instantiation)
# ─────────────────────────────────────────────────────────────────────────────
class MergeErrorType(str, Enum):
    """Types of merge errors during template instantiation."""

    RESOURCE_NOT_FOUND = "resource_not_found"
    FIELD_REQUIRED = "field_required"


class MergeFieldError(BaseModel):
    """Single field merge error."""

    category: str
    rid: str
    field: Optional[str] = None
    error_type: MergeErrorType
    message: str

    model_config = {"frozen": True}


class MergeError(Exception):
    """Raised when template merge fails."""

    def __init__(self, message: str, errors: List[MergeFieldError]):
        super().__init__(message)
        self.message = message
        self.errors = errors

    def __str__(self) -> str:
        return self.message

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert errors to dict list for API responses."""
        return [e.model_dump() for e in self.errors]


# ─────────────────────────────────────────────────────────────────────────────
#  Materialization Errors
# ─────────────────────────────────────────────────────────────────────────────
class MaterializationErrorType(str, Enum):
    """Types of materialization errors."""

    UNKNOWN_ELEMENT_TYPE = "unknown_element_type"
    VALIDATION_FAILED = "validation_failed"
    SAVE_FAILED = "save_failed"


class MaterializationFieldError(BaseModel):
    """Single materialization error."""

    rid: str
    category: Optional[str] = None
    element_type: Optional[str] = None  # Renamed from 'type' to avoid shadowing builtin
    error_type: MaterializationErrorType
    message: str

    model_config = {"frozen": True}

    @classmethod
    def from_resource(
        cls,
        rid: str,
        category: str,
        element_type: str,
        error_type: MaterializationErrorType,
        message: str,
    ) -> "MaterializationFieldError":
        """Create error from resource attributes."""
        return cls(
            rid=rid,
            category=category,
            element_type=element_type,
            error_type=error_type,
            message=message,
        )


class MaterializationError(Exception):
    """Raised when materialization fails."""

    def __init__(self, message: str, errors: List[MaterializationFieldError]):
        super().__init__(message)
        self.message = message
        self.errors = errors

    def __str__(self) -> str:
        return self.message

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert errors to dict list for API responses."""
        return [e.model_dump() for e in self.errors]


# ─────────────────────────────────────────────────────────────────────────────
#  Service-Level Errors
# ─────────────────────────────────────────────────────────────────────────────
class TemplateNotFoundError(Exception):
    """Raised when template is not found."""

    def __init__(self, template_id: str):
        super().__init__(f"Template not found: {template_id}")
        self.template_id = template_id


class TemplateSaveError(Exception):
    """Raised when template save fails."""

    pass


class InstantiationError(Exception):
    """Raised when template instantiation fails."""

    def __init__(self, message: str, errors: List = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []

    def __str__(self) -> str:
        return self.message

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert errors to dict list for API responses."""
        return [self._serialize(e) for e in self.errors]

    @staticmethod
    def _serialize(obj) -> Dict[str, Any]:
        """Serialize any object to dict."""
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return {"error": str(obj)}
