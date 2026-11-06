"""Human administration, bounded dependency publication and atomic curated-resource changes."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from graphlib import CycleError, TopologicalSorter
from typing import Protocol

from pydantic import JsonValue

from mas.application.access.administrators import AdministratorAccess
from mas.application.collaboration.editing import (
    EditEntityKind,
    EditLease,
    EditLockScope,
    EditLockStore,
)
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.identity import Identity
from mas.domain.execution_preferences import ResourceExecutionDefaults
from mas.resources.authoring import ResourcePage, ResourceRecord, ResourceView
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.configuration import ResourceConfiguration
from mas.resources.errors import (
    BuiltinDependentsPublicError,
    ResourceConflictError,
    ResourceInUseError,
    ResourceLockedError,
)
from mas.resources.models import Resource


class BuiltinRepository(Protocol):
    async def get(self, rid: str) -> ResourceRecord: ...
    async def usage(self, rid: str) -> tuple[list[str], list[str]]: ...
    async def list(
        self, category: ResourceCategory | None, type_key: str | None, offset: int, limit: int
    ) -> tuple[list[ResourceRecord], int]: ...
    async def dependents(self, rid: str) -> tuple[ResourceRecord, ...]: ...
    async def commit(
        self,
        observed: tuple[ResourceRecord, ...],
        changed: tuple[ResourceRecord, ...],
        deleted: tuple[str, ...] = (),
    ) -> None:
        """Atomically validate/fence the observed set and apply all resource/descriptor writes."""
        ...


class BuiltinAdministration:
    def __init__(
        self,
        repository: BuiltinRepository,
        administrators: AdministratorAccess,
        configuration: ResourceConfiguration,
        locks: EditLockStore,
        *,
        ttl: int = 180,
        max_dependencies: int = 1000,
    ) -> None:
        self._repository, self._administrators = repository, administrators
        self._configuration, self._locks = configuration, locks
        self._ttl, self._max_dependencies = ttl, max_dependencies

    async def _authorize(self, user: Identity) -> None:
        if not user.is_user or not user.id or not await self._administrators.allowed(user):
            raise PermissionError("Administrator access is required")

    @staticmethod
    def _scope(rid: str) -> EditLockScope:
        return EditLockScope(
            team_id="__builtin_admin__", kind=EditEntityKind.BUILTIN, entity_id=rid
        )

    async def acquire(self, user: Identity, rid: str) -> EditLease | None:
        await self._authorize(user)
        await self._repository.get(rid)
        return await self._locks.acquire(
            self._scope(rid), EditLease(user_id=user.id, display_name=user.id), self._ttl
        )

    async def renew(self, user: Identity, rid: str) -> bool:
        await self._authorize(user)
        await self._repository.get(rid)
        return await self._locks.renew(
            self._scope(rid), EditLease(user_id=user.id, display_name=user.id), self._ttl
        )

    async def release(self, user: Identity, rid: str) -> None:
        await self._authorize(user)
        await self._locks.release(
            self._scope(rid), EditLease(user_id=user.id, display_name=user.id)
        )

    async def _writable(self, user: Identity, rid: str, version: int) -> ResourceRecord:
        await self._authorize(user)
        entry = await self._repository.get(rid)
        if version != entry.resource.version:
            raise ResourceConflictError()
        holder = (await self._locks.holders((self._scope(rid),)))[0]
        if holder is not None and holder.user_id != user.id:
            raise ResourceLockedError(holder.user_id, holder.display_name)
        return entry

    async def list(
        self,
        user: Identity,
        *,
        category: ResourceCategory | None = None,
        type_key: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> ResourcePage:
        await self._authorize(user)
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid curated resource pagination")
        entries, count = await self._repository.list(category, type_key, offset, limit)
        return ResourcePage(
            resources=[self._view(entry) for entry in entries],
            total=count,
            offset=offset,
            limit=limit,
        )

    async def get(self, user: Identity, rid: str) -> ResourceView:
        await self._authorize(user)
        return self._view(await self._repository.get(rid))

    async def create(
        self,
        user: Identity,
        owner: Identity,
        *,
        category: ResourceCategory,
        type_key: str,
        name: str,
        config: dict[str, JsonValue],
        public: bool = False,
        execution: ResourceExecutionDefaults | None = None,
    ) -> tuple[ResourceView, tuple[ResourceView, ...]]:
        await self._authorize(user)
        self._category(category)
        encrypted, refs = await self._configuration.prepare(category, type_key, config)
        resource = Resource(
            identity=owner,
            category=category,
            type=type_key,
            name=name,
            cfg_dict=encrypted,
            nested_refs=refs,
            execution=execution or ResourceExecutionDefaults(),
        )
        entry = ResourceRecord(
            resource=resource, descriptor=BuiltinResourceDescriptor(rid=resource.rid)
        )
        observed, changed = await self._publication(entry) if public else ((), (entry,))
        await self._repository.commit(
            tuple(item for item in observed if item.resource.rid != resource.rid), changed
        )
        return self._view(changed[0]), tuple(self._view(item) for item in changed[1:])

    async def preview(self, user: Identity, rid: str) -> tuple[ResourceView, ...]:
        await self._authorize(user)
        entry = await self._repository.get(rid)
        _, changed = await self._publication(entry)
        return tuple(self._view(item) for item in changed[1:])

    async def update(
        self,
        user: Identity,
        rid: str,
        *,
        expected_version: int,
        config: dict[str, JsonValue] | None = None,
        name: str | None = None,
        public: bool | None = None,
        execution: ResourceExecutionDefaults | None = None,
    ) -> tuple[ResourceView, tuple[ResourceView, ...]]:
        previous = await self._writable(user, rid, expected_version)
        self._category(previous.resource.category)
        updated = previous.model_copy(deep=True)
        if config is not None:
            encrypted, refs = await self._configuration.prepare(
                updated.resource.category, updated.resource.type, config
            )
            updated.resource.cfg_dict, updated.resource.nested_refs = encrypted, refs
        if name is not None:
            updated.resource.name = name
        if execution is not None:
            execution.validate_category(updated.resource.category)
            updated.resource.execution = execution
        updated.resource.version += 1
        updated.resource.updated = datetime.now(UTC)
        ends_public = public if public is not None else self._public(previous)
        if ends_public:
            reads, changed = await self._publication(updated)
            observed = (previous, *(item for item in reads if item.resource.rid != rid))
        else:
            if previous.descriptor is None:
                raise ValueError("Resource is not a built-in")
            await self._no_public_dependents(previous.resource)
            updated.descriptor = previous.descriptor.model_copy(
                update={"visibility": ResourceVisibility.DRAFT, "updated": datetime.now(UTC)}
            )
            observed, changed = (previous,), (updated,)
        await self._repository.commit(tuple(observed), changed)
        return self._view(changed[0]), tuple(self._view(item) for item in changed[1:])

    async def delete(self, user: Identity, rid: str, *, expected_version: int) -> None:
        previous = await self._writable(user, rid, expected_version)
        if previous.descriptor is None:
            raise ValueError("Resource is not a built-in")
        blueprints, resources = await self._repository.usage(rid)
        if blueprints or resources:
            raise ResourceInUseError(by_blueprints=blueprints, by_resources=resources)
        await self._repository.commit((previous,), (), (rid,))

    async def _publication(
        self, root: ResourceRecord
    ) -> tuple[tuple[ResourceRecord, ...], tuple[ResourceRecord, ...]]:
        self._category(root.resource.category)
        entries = {root.resource.rid: root}
        pending = deque(root.resource.nested_refs)
        while pending:
            rid = pending.popleft()
            if rid in entries:
                continue
            if len(entries) >= self._max_dependencies:
                raise ValueError("Curated dependency graph exceeds its limit")
            entry = await self._repository.get(rid)
            self._category(entry.resource.category)
            _, references = await self._configuration.prepare(
                entry.resource.category, entry.resource.type, entry.resource.cfg_dict
            )
            if set(references) != set(entry.resource.nested_refs):
                raise ValueError("Stored construction references are inconsistent")
            entries[rid] = entry
            pending.extend(entry.resource.nested_refs)
        try:
            tuple(
                TopologicalSorter(
                    {rid: set(entry.resource.nested_refs) for rid, entry in entries.items()}
                ).static_order()
            )
        except CycleError:
            raise ValueError("Cyclic resource construction dependencies") from None
        changed = []
        for entry in entries.values():
            if entry is not root and self._public(entry):
                continue
            updated = entry.model_copy(deep=True)
            descriptor = updated.descriptor or BuiltinResourceDescriptor(rid=updated.resource.rid)
            updated.descriptor = descriptor.model_copy(
                update={"visibility": ResourceVisibility.PUBLIC, "updated": datetime.now(UTC)}
            )
            if entry is not root:
                updated.resource.version += 1
                updated.resource.updated = datetime.now(UTC)
            changed.append(updated)
        return tuple(entries.values()), tuple(changed)

    async def _no_public_dependents(self, resource: Resource) -> None:
        pending, visited, public = deque([resource.rid]), {resource.rid}, []
        while pending:
            for entry in await self._repository.dependents(pending.popleft()):
                rid = entry.resource.rid
                if rid in visited:
                    continue
                visited.add(rid)
                if len(visited) > self._max_dependencies:
                    raise ValueError("Curated dependent graph exceeds its limit")
                if self._public(entry):
                    public.append(entry.resource)
                pending.append(rid)
        if public:
            raise BuiltinDependentsPublicError(
                resource_name=resource.name, category=resource.category.value, dependents=public
            )

    @staticmethod
    def _public(entry: ResourceRecord) -> bool:
        return (
            entry.descriptor is not None
            and entry.descriptor.visibility == ResourceVisibility.PUBLIC
        )

    @staticmethod
    def _category(category: ResourceCategory) -> None:
        if category in ResourceCategory.builtin_disabled_categories():
            raise ValueError("Category does not support curated resources")

    @staticmethod
    def _view(entry: ResourceRecord) -> ResourceView:
        return ResourceView(
            **entry.resource.model_dump(),
            ownership=ResourceOwnership.BUILTIN if entry.descriptor else ResourceOwnership.CUSTOM,
            visibility=entry.descriptor.visibility if entry.descriptor else None,
        )
