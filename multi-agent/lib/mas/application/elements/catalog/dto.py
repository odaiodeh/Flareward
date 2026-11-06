from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ElementSummaryDTO:
    """
    DTO for element summary information (used in list endpoints).
    Contains basic element identification and metadata.
    """

    category: str
    type: str  # Using 'type' instead of 'type_key' for better UI compatibility
    name: str
    hints: list


@dataclass(frozen=True)
class ElementDetailDTO:
    """
    DTO for detailed element information (used when requesting specific element spec).
    Contains all information needed for UI forms and configuration.
    """

    name: str
    category: str
    description: str
    type: str  # Using 'type' instead of 'type_key' for better UI compatibility
    config_schema: dict[str, Any]  # JSON schema for dynamic form generation
    tags: list[str]
    output_schema: dict[str, Any] | None = (
        None  # Output schema for conditions and other elements that define outputs
    )
    input_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class CatalogListDTO:
    """
    DTO for catalog list response.
    Groups elements by category for UI organization.
    """

    elements: dict[str, list[ElementSummaryDTO]]  # category -> list of elements
