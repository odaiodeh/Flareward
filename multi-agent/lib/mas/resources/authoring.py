"""Native resource editing keeps application policy separate from storage and element factories."""

import asyncio
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, Field, JsonValue, ValidationError

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.async_work import await_owned
from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.execution_preferences import ResourceExecutionDefaults
from mas.core.identity import Identity
from mas.core.ref import RefWalker
from mas.resources.access import require_custom_write, require_visible
from mas.resources.builtin_models import (
    BuiltinResourceDescriptor,
    BuiltinUserConfig,
    identity_to_key,
)
from mas.resources.errors import ResourceConflictError, ResourceInUseError
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.models import Resource


class ResourceRecord(BaseModel):
    resource: Resource
    descriptor: BuiltinResourceDescriptor | None = None


class ResourceView(Resource):
    ownership: ResourceOwnership
    visibility: ResourceVisibility | None = None
    user_configured: bool = False


class ResourcePage(BaseModel):
    resources: list[ResourceView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=1000)


class ResourceAuthoringRepository(Protocol):
    async def create(self, resource: Resource) -> None: ...
    async def get(self, rid: str) -> ResourceRecord: ...
    async def replace(self, previous: Resource, updated: Resource) -> bool: ...
    async def delete(self, previous: Resource) -> bool: ...
    async def usage(self, rid: str) -> tuple[list[str], list[str]]: ...
    async def list(
        self,
        caller: Identity,
        *,
        category: ResourceCategory | None,
        type_key: str | None,
        ownership: ResourceOwnership | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ResourceRecord], int]: ...


class BuiltinConfigurationRepository(Protocol):
    async def get(self, rid: str, identity_key: str) -> BuiltinUserConfig | None: ...
    async def list(self, identity_key: str) -> list[BuiltinUserConfig]: ...
    async def replace(
        self, previous: BuiltinUserConfig | None, updated: BuiltinUserConfig
    ) -> bool: ...


class ResourceAuthoringService:
    def __init__(
        self,
        repository: ResourceAuthoringRepository,
        elements: ElementRegistry,
        fields: ResourceFieldEncryption,
        overlays: BuiltinConfigurationRepository | None = None,
    ) -> None:
        self._repository, self._elements, self._fields = repository, elements, fields
        self._overlays = overlays

    def schema(self, category: ResourceCategory, type_key: str) -> dict:
        return self._elements.get_schema_json(category, type_key)

    async def create(
        self,
        caller: Identity,
        *,
        category: ResourceCategory,
        type_key: str,
        name: str,
        config: dict[str, JsonValue],
        execution: ResourceExecutionDefaults | None = None,
    ) -> ResourceView:
        encrypted, references = await self._prepare(category, type_key, config)
        resource = Resource(
            identity=caller,
            category=category,
            type=type_key,
            name=name,
            cfg_dict=encrypted,
            nested_refs=references,
            execution=execution or ResourceExecutionDefaults(),
        )
        await self._repository.create(resource)
        return self._view(ResourceRecord(resource=resource))

    async def get(self, rid: str, caller: Identity) -> ResourceView:
        entry = await self._repository.get(rid)
        require_visible(entry.resource, entry.descriptor, CallerScope(identity=caller))
        overlay = (
            await self._overlays.get(rid, identity_to_key(caller))
            if entry.descriptor is not None and self._overlays is not None
            else None
        )
        return await await_owned(asyncio.to_thread(self._view, entry, overlay))

    async def list(
        self,
        caller: Identity,
        *,
        category: ResourceCategory | None = None,
        type_key: str | None = None,
        ownership: ResourceOwnership | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> ResourcePage:
        if offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("Invalid resource pagination")
        entries, total = await self._repository.list(
            caller,
            category=category,
            type_key=type_key,
            ownership=ownership,
            offset=offset,
            limit=limit,
        )
        overlays = (
            {item.resource_id: item for item in await self._overlays.list(identity_to_key(caller))}
            if self._overlays is not None and any(entry.descriptor is not None for entry in entries)
            else {}
        )
        views = await await_owned(
            asyncio.to_thread(
                lambda: [self._view(entry, overlays.get(entry.resource.rid)) for entry in entries]
            )
        )
        return ResourcePage(
            resources=views,
            total=total,
            offset=offset,
            limit=limit,
        )

    async def update(
        self,
        rid: str,
        caller: Identity,
        *,
        config: dict[str, JsonValue],
        name: str | None = None,
        expected_version: int | None = None,
        execution: ResourceExecutionDefaults | None = None,
    ) -> ResourceView:
        previous = await self._writable(rid, caller, expected_version)
        encrypted, references = await self._prepare(previous.category, previous.type, config)
        updated = Resource.model_validate(
            {
                **dict(previous),
                "name": name if name is not None else previous.name,
                "cfg_dict": encrypted,
                "nested_refs": references,
                "version": previous.version + 1,
                "updated": datetime.now(UTC),
                "execution": execution if execution is not None else previous.execution,
            }
        )
        if not await self._repository.replace(previous, updated):
            raise ResourceConflictError()
        return self._view(ResourceRecord(resource=updated))

    async def delete(
        self, rid: str, caller: Identity, *, expected_version: int | None = None
    ) -> None:
        previous = await self._writable(rid, caller, expected_version)
        blueprints, resources = await self._repository.usage(rid)
        if blueprints or resources:
            raise ResourceInUseError(by_blueprints=blueprints, by_resources=resources)
        if not await self._repository.delete(previous):
            raise ResourceConflictError()

    async def _writable(self, rid: str, caller: Identity, expected_version: int | None) -> Resource:
        entry = await self._repository.get(rid)
        require_custom_write(entry.resource, entry.descriptor, CallerScope(identity=caller))
        if expected_version is not None and expected_version != entry.resource.version:
            raise ResourceConflictError()
        return entry.resource

    async def configuration(self, rid: str, caller: Identity) -> BuiltinUserConfig | None:
        entry = await self._public_builtin(rid, caller)
        overlay = await self._overlay_store().get(rid, identity_to_key(caller))
        if overlay is not None:
            overlay = overlay.model_copy(
                update={"fields": self._allowed_fields(entry, overlay.fields)}
            )
        return overlay

    async def configure(
        self,
        rid: str,
        caller: Identity,
        *,
        config: dict[str, JsonValue],
        expected_version: int | None = None,
    ) -> BuiltinUserConfig:
        entry = await self._public_builtin(rid, caller)
        repository = self._overlay_store()
        previous = await repository.get(rid, identity_to_key(caller))
        version = previous.version if previous is not None else 0
        if expected_version is not None and expected_version != version:
            raise ResourceConflictError()
        config = self._fields.canonical_fields(entry.resource.category, entry.resource.type, config)
        filtered = self._allowed_fields(entry, config)
        if not filtered or filtered.keys() != config.keys():
            raise ValueError("Provide only caller-configurable fields")

        def prepare() -> dict:
            base = self._fields.strip_unconfigured_secrets(
                entry.resource.category,
                entry.resource.type,
                self._fields.decrypt(entry.resource.cfg_dict),
            )
            existing = self._allowed_fields(entry, previous.fields) if previous is not None else {}
            values = {**existing, **filtered}
            schema = self._elements.get_schema(entry.resource.category, entry.resource.type)
            try:
                model = schema.model_validate(
                    {**base, **self._fields.decrypt(values)}, by_name=True
                )
            except ValidationError:
                raise ValueError("Invalid built-in configuration") from None
            encrypted = self._fields.encrypt_model(model)
            return {name: encrypted[name] for name in values}

        encrypted = await await_owned(asyncio.to_thread(prepare))
        updated = (
            previous.model_copy(deep=True)
            if previous is not None
            else BuiltinUserConfig(resource_id=rid, identity_key=identity_to_key(caller))
        )
        updated.fields, updated.version, updated.updated = encrypted, version + 1, datetime.now(UTC)
        if not await repository.replace(previous, updated):
            raise ResourceConflictError()
        return updated

    async def reset_configuration(
        self, rid: str, caller: Identity, *, expected_version: int | None = None
    ) -> None:
        await self._public_builtin(rid, caller)
        repository = self._overlay_store()
        previous = await repository.get(rid, identity_to_key(caller))
        version = previous.version if previous is not None else 0
        if expected_version is not None and expected_version != version:
            raise ResourceConflictError()
        if previous is not None:
            cleared = previous.model_copy(
                update={"fields": {}, "version": version + 1, "updated": datetime.now(UTC)}
            )
            if not await repository.replace(previous, cleared):
                raise ResourceConflictError()

    async def _public_builtin(self, rid: str, caller: Identity) -> ResourceRecord:
        entry = await self._repository.get(rid)
        require_visible(entry.resource, entry.descriptor, CallerScope(identity=caller))
        if entry.descriptor is None:
            raise ValueError("Resource is not a built-in")
        return entry

    def _overlay_store(self) -> BuiltinConfigurationRepository:
        if self._overlays is None:
            raise ValueError("Built-in configuration is not enabled")
        return self._overlays

    def _allowed_fields(self, entry: ResourceRecord, config: dict) -> dict:
        configurable, _ = self._fields.scan_schema_hints(
            entry.resource.category, entry.resource.type
        )
        allowed = configurable | self._fields.auth_metadata_keys(
            entry.resource.category, entry.resource.type
        )
        return {name: value for name, value in config.items() if name in allowed}

    async def _prepare(
        self, category: ResourceCategory, type_key: str, config: dict[str, JsonValue]
    ) -> tuple[dict, list[str]]:
        schema = self._elements.get_schema(category, type_key)

        def normalize() -> tuple[dict, list[str]]:
            try:
                model = schema.model_validate(self._fields.decrypt(config), by_name=True)
            except ValidationError:
                raise ValueError(f"Invalid configuration for {type_key}") from None
            references = sorted(set(RefWalker.external_rids(model)))
            return self._fields.encrypt_model(model), references

        return await await_owned(asyncio.to_thread(normalize))

    def _view(
        self, entry: ResourceRecord, overlay: BuiltinUserConfig | None = None
    ) -> ResourceView:
        data = entry.resource.model_dump(mode="python")
        if entry.descriptor is not None:
            data["cfg_dict"] = self._fields.public_config(
                entry.resource.category, entry.resource.type, entry.resource.cfg_dict
            )
            if overlay is not None:
                data["cfg_dict"].update(self._allowed_fields(entry, overlay.fields))
        return ResourceView(
            **data,
            ownership=ResourceOwnership.BUILTIN
            if entry.descriptor is not None
            else ResourceOwnership.CUSTOM,
            visibility=entry.descriptor.visibility if entry.descriptor is not None else None,
            user_configured=overlay is not None
            and bool(self._allowed_fields(entry, overlay.fields)),
        )
