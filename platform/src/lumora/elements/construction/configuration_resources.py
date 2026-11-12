"""Capture saved capabilities into declared configuration bundle fields."""

from collections.abc import Mapping
from copy import deepcopy

from pydantic import BaseModel, JsonValue

from lumora.elements.construction.drafts import ConfigurationDraft
from lumora.elements.construction.snapshots import ResourceSelection, SavedResourceResolver
from lumora.resources.domain.bundles import ElementBundle
from lumora.resources.secrets import serialized_key
from lumora.services.identity.domain import Identity

type ConfigurationPath = tuple[str | int, ...]


class ConfigurationResources:
    def __init__(self, snapshots: SavedResourceResolver) -> None:
        self._snapshots = snapshots

    async def capture(
        self,
        schema: type[BaseModel],
        data: dict[str, JsonValue],
        selections: Mapping[ConfigurationPath, ResourceSelection],
        caller: Identity,
    ) -> dict[str, JsonValue]:
        previous_configuration = ConfigurationDraft.parse(schema, data)
        updated = deepcopy(data)
        captured: dict[ConfigurationPath, ElementBundle] = {}
        for path, selection in selections.items():
            canonical, previous = self._typed_location(previous_configuration, path)
            holder: dict[str, JsonValue] = {"config": updated}
            parent, key = self._destination(holder, ("config", *canonical))
            existing = previous if isinstance(previous, ElementBundle) else None
            bundle = await self._snapshots.bundle(selection, caller, existing=existing)
            parent[key] = bundle.model_dump(mode="json")
            updated = holder["config"]
            captured[path] = bundle
        # Check the actual selected model/union branch, not a title in JSON Schema.
        configuration = ConfigurationDraft.parse(schema, updated)
        destinations: set[int] = set()
        for path, expected in captured.items():
            _, selected = self._typed_location(configuration, path)
            if not isinstance(selected, ElementBundle) or selected != expected:
                raise ValueError("Resource selection must identify a declared ElementBundle field")
            if id(selected) in destinations:
                raise ValueError("Select each configuration resource field only once")
            destinations.add(id(selected))
        return updated

    @staticmethod
    def _destination(
        data: dict[str, JsonValue], path: ConfigurationPath
    ) -> tuple[dict[str, JsonValue] | list[JsonValue], str | int]:
        if not path:
            raise ValueError("Resource selection requires a configuration field path")
        current = data
        for index, part in enumerate(path):
            final = index == len(path) - 1
            if isinstance(current, dict) and isinstance(part, str):
                if final:
                    return current, part
                if part not in current or current[part] is None:
                    # Missing object fields can be authored; arrays must already exist.
                    current[part] = {}
                current = current[part]
            elif isinstance(current, list) and type(part) is int and 0 <= part < len(current):
                if final:
                    return current, part
                current = current[part]
            else:
                raise ValueError("Resource selection identifies an unavailable configuration field")
        raise ValueError("Invalid configuration field path")

    @classmethod
    def _typed_location(
        cls, value: object, path: ConfigurationPath
    ) -> tuple[ConfigurationPath, object]:
        if not path:
            return (), value
        if isinstance(value, (BaseModel, ConfigurationDraft)):
            schema = value.schema if isinstance(value, ConfigurationDraft) else type(value)
            for name, field in schema.model_fields.items():
                for alias in ConfigurationDraft.field_paths(
                    name, field, by_alias=schema.model_config.get("validate_by_alias", True)
                ):
                    prefix = tuple(alias.path)
                    if path[: len(prefix)] == prefix:
                        child = (
                            value.values.get(name)
                            if isinstance(value, ConfigurationDraft)
                            else getattr(value, name)
                        )
                        tail, selected = cls._typed_location(child, path[len(prefix) :])
                        return (name, *tail), selected
        elif isinstance(value, dict):
            for key, child in value.items():
                if serialized_key(key) == path[0]:
                    tail, selected = cls._typed_location(child, path[1:])
                    return (serialized_key(key), *tail), selected
        elif (
            isinstance(value, (list, tuple)) and type(path[0]) is int and 0 <= path[0] < len(value)
        ):
            tail, selected = cls._typed_location(value[path[0]], path[1:])
            return (path[0], *tail), selected
        # An absent draft value can be supplied; validate its actual type after capture.
        return path, None
