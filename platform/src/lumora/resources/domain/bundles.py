"""Configuration-only resource bundles. Runtime capabilities travel separately."""

import hashlib
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from lumora.resources.domain.categories import ResourceCategory


def _identity_numbers(value: JsonValue) -> JsonValue:
    """Hash equivalent JSON numbers alike without changing authored configuration."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_identity_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _identity_numbers(item) for key, item in value.items()}
    return value


class ResourceKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    category: ResourceCategory
    rid: str = Field(min_length=1)


class ResourceSourceRef(BaseModel):
    """An owner-scoped revision of saved configuration, including its caller overlay."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    key: ResourceKey
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResourceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    key: ResourceKey
    type_key: str = Field(min_length=1)
    name: str = ""
    config: dict[str, JsonValue] = Field(default_factory=dict)
    implementation_version: str = "1.0.0"


class BundleEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    resource: ResourceDefinition
    dependencies: tuple[ResourceKey, ...] = ()


class ElementBundle(BaseModel):
    """Entries are in construction order, with a digest checked at every boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2] = 2
    root: ResourceKey
    entries: tuple[BundleEntry, ...]
    content_digest: str = ""

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        seen: set[ResourceKey] = set()
        for entry in self.entries:
            key = entry.resource.key
            if key in seen:
                raise ValueError(f"Duplicate resource: {key}")
            if not set(entry.dependencies) <= seen:
                raise ValueError(f"Dependencies must precede resource: {key}")
            seen.add(key)
        if self.root not in seen:
            raise ValueError("Bundle root is missing")
        by_key = {entry.resource.key: entry for entry in self.entries}
        reachable: set[ResourceKey] = set()

        pending = [self.root]
        while pending:
            key = pending.pop()
            if key not in reachable:
                reachable.add(key)
                pending.extend(by_key[key].dependencies)
        if reachable != seen:
            raise ValueError("Bundle contains resources unrelated to its root")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(
            _identity_numbers(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if self.content_digest and self.content_digest != digest:
            raise ValueError("Element bundle digest does not match its contents")
        object.__setattr__(self, "content_digest", digest)
        return self
