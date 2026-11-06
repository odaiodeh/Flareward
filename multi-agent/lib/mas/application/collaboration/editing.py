"""Cooperative team editing leases, separate from session presence and transport."""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from mas.blueprints.authoring import BlueprintAuthoringService
from mas.core.identity import Identity
from mas.resources.authoring import ResourceAuthoringService


class EditEntityKind(StrEnum):
    RESOURCE = "resource"
    BLUEPRINT = "blueprint"
    BUILTIN = "builtin"


class EditLockScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    team_id: str = Field(min_length=1)
    kind: EditEntityKind
    entity_id: str = Field(min_length=1)


class EditLease(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_id: str = Field(min_length=1)
    display_name: str
    lease_id: str | None = Field(default=None, min_length=1, max_length=128)


class EditLockUnavailable(RuntimeError):
    """Lock state is unavailable; callers must not assume that it is unlocked."""


class EditLockStore(Protocol):
    async def acquire(
        self, scope: EditLockScope, lease: EditLease, ttl: int
    ) -> EditLease | None: ...
    async def renew(self, scope: EditLockScope, lease: EditLease, ttl: int) -> bool: ...
    async def release(self, scope: EditLockScope, lease: EditLease) -> None: ...
    async def holders(self, scopes: tuple[EditLockScope, ...]) -> tuple[EditLease | None, ...]: ...


class TeamEditService:
    def __init__(
        self,
        store: EditLockStore,
        resources: ResourceAuthoringService,
        blueprints: BlueprintAuthoringService,
        *,
        ttl: int = 180,
    ) -> None:
        self._store, self._resources, self._blueprints = store, resources, blueprints
        self._ttl = ttl

    @staticmethod
    def scope(owner: Identity, kind: EditEntityKind, entity_id: str) -> EditLockScope:
        if not owner.is_team or kind == EditEntityKind.BUILTIN:
            raise PermissionError("Editing leases require an authorized team workspace")
        return EditLockScope(team_id=owner.id, kind=kind, entity_id=entity_id)

    async def _authorize(self, owner: Identity, scope: EditLockScope) -> None:
        read = (
            self._resources.get if scope.kind == EditEntityKind.RESOURCE else self._blueprints.get
        )
        entity = await read(scope.entity_id, owner)
        if not owner.owns(entity.identity):
            raise PermissionError("The selected team does not own this entity")

    async def acquire(
        self,
        owner: Identity,
        kind: EditEntityKind,
        entity_id: str,
        lease: EditLease,
    ) -> EditLease | None:
        scope = self.scope(owner, kind, entity_id)
        await self._authorize(owner, scope)
        return await self._store.acquire(scope, lease, self._ttl)

    async def renew(
        self,
        owner: Identity,
        kind: EditEntityKind,
        entity_id: str,
        lease: EditLease,
    ) -> bool:
        scope = self.scope(owner, kind, entity_id)
        await self._authorize(owner, scope)
        return await self._store.renew(scope, lease, self._ttl)

    async def release(
        self,
        owner: Identity,
        kind: EditEntityKind,
        entity_id: str,
        lease: EditLease,
    ) -> None:
        # Deletion may already have removed the entity; the lease comparison still fences release.
        await self._store.release(self.scope(owner, kind, entity_id), lease)

    async def holders(
        self,
        owner: Identity,
        kind: EditEntityKind,
        entity_ids: tuple[str, ...],
    ) -> dict[str, EditLease | None]:
        scopes = tuple(self.scope(owner, kind, entity_id) for entity_id in entity_ids)
        if not scopes and not owner.is_team:
            raise PermissionError("Editing leases require an authorized team workspace")
        for scope in scopes:
            await self._authorize(owner, scope)
        return dict(zip(entity_ids, await self._store.holders(scopes), strict=True))
