import threading

from pydantic import BaseModel

from mas.application.elements.specification import BaseElementSpec, BaseFactory
from mas.core.enums import ResourceCategory


class ElementRegistry:
    """
    Application-owned catalog of element implementations.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Map each ResourceCategory to a dict of type_key -> spec class
        self._specs: dict[ResourceCategory, dict[str, type[BaseElementSpec]]] = {}

    # ------------------------------------------------------------------ #
    #  Registration & Access Public API
    # ------------------------------------------------------------------ #
    def register_spec_class(self, spec_cls: type[BaseElementSpec]) -> None:
        """Compose identical registrations idempotently; reject conflicting implementations."""
        if spec_cls.category == ResourceCategory.SANDBOX:
            raise ValueError("Sandbox elements are retired; select an execution profile")
        with self._lock:
            categories_map = self._specs.setdefault(spec_cls.category, {})
            existing = categories_map.get(spec_cls.type_key)
            if existing is not None and existing is not spec_cls:
                raise ValueError(
                    f"Spec already registered: {spec_cls.category}/{spec_cls.type_key}"
                )
            categories_map[spec_cls.type_key] = spec_cls

    def get_spec(self, category: ResourceCategory, type_key: str) -> type[BaseElementSpec]:
        """Retrieve the spec class for a given category and type_key."""
        try:
            return self._specs[category][type_key]
        except KeyError:
            raise KeyError(f"No spec registered for {category}/{type_key}")

    def has_spec(self, category: ResourceCategory, type_key: str) -> bool:
        """Returns True if a spec class is registered for the given category and type_key."""
        return type_key in self._specs.get(category, {})

    def get_categories_map(self) -> dict[ResourceCategory, dict[str, type[BaseElementSpec]]]:
        """Return a detached catalog snapshot; registration remains the only write path."""
        with self._lock:
            return {
                category: dict(specifications) for category, specifications in self._specs.items()
            }

    def get_category_types_map(self) -> dict[str, list[str]]:
        """
        Return a mapping of category names to their available type keys.

        Returns:
            Dict mapping category enum values (e.g., "LLMS", "NODES") to lists of type keys
            Example: {"LLMS": ["openai_llm", "mock_llm"], "NODES": ["custom_agent_node", ...]}
        """
        with self._lock:
            result = {}
            for category, types_map in self._specs.items():
                # Get the enum value (e.g., "LLMS" instead of ResourceCategory.LLMS)
                category_name = category.value if hasattr(category, "value") else str(category)
                # Get all type keys for this category
                type_keys = list(types_map.keys())
                result[category_name] = type_keys
            return result

    def list_categories(self) -> list[ResourceCategory]:
        """List all registered ResourceCategory values."""
        return list(self._specs.keys())

    def list_types(self, category: ResourceCategory) -> list[str]:
        """List all registered type_keys for a given category."""
        return list(self._specs.get(category, {}).keys())

    def get_schema_json(self, category: ResourceCategory, type_key: str) -> dict:
        """Return the JSON schema of the config_model for the spec class."""
        spec_cls = self.get_spec(category, type_key)
        return spec_cls.config_schema.model_json_schema()

    def get_schema(self, category: ResourceCategory, type_key: str) -> type[BaseModel]:
        """Return the Pydantic model class (config_schema) for the spec."""
        spec_cls = self.get_spec(category, type_key)
        return spec_cls.config_schema

    def get_factory_class(self, category: ResourceCategory, type_key: str) -> type[BaseFactory]:
        """Return the factory class associated with the spec."""
        spec_cls = self.get_spec(category, type_key)
        return spec_cls.factory_cls
