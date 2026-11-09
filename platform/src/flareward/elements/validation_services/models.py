"""
validation/models.py

Models for validation orchestration (service-level).
Element-level models live in elements/common/validator.py
"""

from pydantic import BaseModel, Field

from flareward.elements.validation import ElementValidationResult


class BlueprintValidationResult(BaseModel):
    """Result of validating an entire blueprint."""

    blueprint_id: str
    is_valid: bool
    element_results: dict[str, ElementValidationResult] = Field(default_factory=dict)
