from typing import Any

from flareward.elements.catalog.dto import CatalogListDTO, ElementDetailDTO, ElementSummaryDTO
from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.resources.domain.categories import ResourceCategory


class CatalogService:
    """
    Enhanced catalog service
    Converts registry information into JSON-serialisable shapes the UI likes.
    """

    def __init__(self, registry: ElementRegistry):
        self.reg = registry

    def get_all_elements_summary(self) -> CatalogListDTO:
        """Get all elements as summary DTOs, organized by category."""
        elements_by_category = {}

        for category in self.reg.list_categories():
            category_name = category.value if hasattr(category, "value") else str(category)
            elements = []

            for type_key in self.reg.list_types(category):
                spec_cls = self.reg.get_spec(category, type_key)
                if getattr(spec_cls, "hidden", False):
                    continue
                elements.append(
                    ElementSummaryDTO(
                        category=category_name,
                        type=type_key,
                        name=spec_cls.name,
                        hints=spec_cls.hints if hasattr(spec_cls, "hints") else [],
                    )
                )

            if elements:
                elements_by_category[category_name] = elements

        return CatalogListDTO(elements=elements_by_category)

    def get_element_detail(self, category: str, type_key: str) -> ElementDetailDTO:
        """Get detailed element information for a specific element"""
        cat_enum = ResourceCategory(category)
        spec_cls = self.reg.get_spec(cat_enum, type_key)

        # Check if the spec has an output_schema attribute (duck typing approach)
        output_schema = None
        if hasattr(spec_cls, "output_schema"):
            # Convert the output schema to JSON schema format
            output_schema = (
                spec_cls.output_schema.model_dump()
                if hasattr(spec_cls.output_schema, "model_dump")
                else spec_cls.output_schema
            )
        if spec_cls.result_schema is not None:
            output_schema = spec_cls.result_schema.model_json_schema(
                mode="serialization", by_alias=False
            )

        return ElementDetailDTO(
            name=spec_cls.name,
            category=category,
            description=spec_cls.description,
            type=type_key,
            config_schema=spec_cls.config_schema.model_json_schema(),
            tags=spec_cls.tags,
            output_schema=output_schema,
            input_schema=spec_cls.input_schema.model_json_schema()
            if spec_cls.input_schema is not None
            else None,
        )

    def list_categories(self) -> list[str]:
        """List all available element categories."""
        return [c.value if hasattr(c, "value") else str(c) for c in self.reg.list_categories()]

    def list_types(self, category: str) -> list[str]:
        """List all element types in a category"""
        cat_enum = ResourceCategory(category)
        return self.reg.list_types(cat_enum)

    def get_schema_json(self, category: str, type_key: str) -> dict[str, Any]:
        """Get JSON schema for an element type (works with both specs and legacy)"""
        cat_enum = ResourceCategory(category)
        return self.reg.get_schema_json(cat_enum, type_key)

    def get_description(self, category: str, type_key: str) -> str:
        """Get description for an element type"""
        cat_enum = ResourceCategory(category)

        # Try spec first (new system)
        if self.reg.has_spec(cat_enum, type_key):
            spec = self.reg.get_spec(cat_enum, type_key)
            return spec.description
