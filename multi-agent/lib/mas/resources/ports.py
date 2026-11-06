"""
Ports (interfaces) for external dependencies of the resources domain.

Services and adapters depend on these ABCs rather than concrete
implementations, keeping the dependency arrows pointing inward.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from mas.application.elements.validation import ElementValidationResult
from mas.collaboration.models import TeamEditLockHolder
from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
from mas.domain.element_card import ElementCard
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.models import Resource


class BlueprintUsageReader(Protocol):
    """The resource library only needs blueprint references for deletion guards."""

    def list_direct_usage(self, rid: str) -> list[str]: ...


@runtime_checkable
class CredentialCleanupPort(Protocol):
    """Capability to delete stored credentials when no resource references them."""

    def delete_credential(self, user_id: str, server_identifier: str) -> None: ...


@runtime_checkable
class ResourceServicePort(Protocol):
    """Contract shared by CoreResourceService and BuiltinAwareResourceService.

    Every consumer — Flask endpoints, BlueprintResolver, ShareCloner —
    depends on this protocol, never on a concrete service class.
    """

    def get_visible(self, rid: str, *, caller: CallerScope) -> Resource: ...

    def find_resources(
        self,
        category: str | None = ...,
        type: str | None = ...,
        ownership: str | None = ...,
        limit: int = ...,
        offset: int = ...,
        caller: CallerScope = ...,
    ) -> tuple[list[dict], int]: ...

    def resolve(self, rid: str, caller: CallerScope = ...) -> BaseModel: ...

    def resolve_resource(self, resource: Resource, caller: CallerScope = ...) -> BaseModel: ...

    def validate_resource(
        self,
        rid: str,
        caller: CallerScope = ...,
        user_id: str = ...,
        timeout_seconds: float = ...,
        credential_user_id: str = ...,
    ) -> ElementValidationResult: ...

    def get_card(self, rid: str, caller: CallerScope = ...) -> ElementCard: ...

    def get_cards(
        self,
        rids: list[str],
        caller: CallerScope = ...,
    ) -> dict[str, ElementCard]: ...

    def guard_write_access(
        self,
        rid: str,
        caller: CallerScope,
        *,
        username: str = ...,
    ) -> Resource: ...

    def create(
        self,
        *,
        identity: Identity,
        category: str,
        type: str,
        name: str,
        config: dict,
    ) -> Resource: ...

    def update(self, rid: str, *, config: dict, name: str | None = ...) -> Resource: ...

    def delete(self, rid: str) -> None: ...

    def to_dict(
        self,
        resource: Resource,
        *,
        identity: Identity | None = ...,
    ) -> dict: ...


@runtime_checkable
class ResourceReader(Protocol):
    """Narrow read port: fetch a visibility-gated resource and resolve its config.

    This is all ``BlueprintResolver`` needs — it depends on this Protocol
    (satisfied structurally by ``CoreResourceService`` and
    ``BuiltinAwareResourceService``) rather than the full service, so its
    dependency graph doesn't implicitly grow every time the service gains
    an unrelated CRUD/validation/card concern.
    """

    def get_visible(self, rid: str, *, caller: CallerScope) -> Resource: ...

    def resolve_resource(self, resource: Resource, caller: CallerScope) -> BaseModel: ...


@runtime_checkable
class ResourceClonePort(Protocol):
    """Narrow port for cloning: raw fetch, create, name-conflict check, delete.

    This is all ``ShareCloner`` needs. Unlike ``BlueprintResolver`` it never
    calls ``get_visible``/``resolve_resource`` — it works with resources it
    already owns (or is authorized to clone) and builds config models itself
    via ``ElementRegistry``, so it gets its own narrow port rather than
    sharing ``ResourceReader``.
    """

    def get(self, rid: str) -> Resource: ...

    def save_resource(self, resource: Resource) -> Resource: ...

    def exists_by_name(
        self,
        identity: Identity,
        category: str,
        type_: str,
        name: str,
    ) -> bool: ...

    def delete(self, rid: str) -> None: ...


@runtime_checkable
class BuiltinDescriptorReader(Protocol):
    """Narrow read port for checking whether a resource is a built-in.

    Sharing only reads descriptor metadata; it does not own administration.
    """

    def get(self, rid: str) -> BuiltinResourceDescriptor | None: ...


@runtime_checkable
class AdminEditLockReader(Protocol):
    """Narrow read port for checking whether a built-in resource is locked.

    ``BuiltinAwareResourceService.guard_write_access`` uses this to reject
    mutations when another admin holds the cooperative edit lock — satisfied
    structurally by ``AdminEditLockService``.
    """

    def get_admin_edit_lock(self, entity_id: str) -> TeamEditLockHolder | None: ...
