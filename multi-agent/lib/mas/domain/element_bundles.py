"""Configuration-only resource bundles. Runtime capabilities travel separately."""

import hashlib
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from mas.core.enums import ResourceCategory


class ResourceKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    category: ResourceCategory
    rid: str = Field(min_length=1)


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
    schema_version: Literal[1] = 1
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

        def visit(key: ResourceKey) -> None:
            if key not in reachable:
                reachable.add(key)
                for dependency in by_key[key].dependencies:
                    visit(dependency)

        visit(self.root)
        if reachable != seen:
            raise ValueError("Bundle contains resources unrelated to its root")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if self.content_digest and self.content_digest != digest:
            raise ValueError("Element bundle digest does not match its contents")
        object.__setattr__(self, "content_digest", digest)
        return self
