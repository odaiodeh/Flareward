"""One schema-driven configuration preparation path for custom and curated resources."""

import asyncio
from copy import deepcopy
from typing import Any

from pydantic import JsonValue, ValidationError

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.async_work import await_owned
from mas.core.enums import ResourceCategory
from mas.core.ref.walker import RefWalker
from mas.resources.field_encryption import ResourceFieldEncryption


class ResourceConfiguration:
    def __init__(self, elements: ElementRegistry, fields: ResourceFieldEncryption) -> None:
        self._elements, self._fields = elements, fields

    def schema(
        self, category: ResourceCategory, type_key: str, *, configurable_only: bool = False
    ) -> dict[str, Any]:
        schema = deepcopy(self._elements.get_schema_json(category, type_key))
        if configurable_only:
            configurable, _ = self._fields.scan_schema_hints(category, type_key)
            for name, field in schema.get("properties", {}).items():
                hints = field.setdefault("hints", {})
                if name not in configurable and "hidden" not in hints:
                    hints["read_only"] = {"read_only": True}
        return schema

    async def prepare(
        self, category: ResourceCategory, type_key: str, config: dict[str, JsonValue]
    ) -> tuple[dict[str, JsonValue], list[str]]:
        schema = self._elements.get_schema(category, type_key)

        def normalize() -> tuple[dict[str, JsonValue], list[str]]:
            try:
                model = schema.model_validate(self._fields.decrypt(config), by_name=True)
            except ValidationError:
                raise ValueError(f"Invalid configuration for {type_key}") from None
            return self._fields.encrypt_model(model), sorted(set(RefWalker.external_rids(model)))

        return await await_owned(asyncio.to_thread(normalize))
