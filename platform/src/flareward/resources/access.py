"""Resource visibility and generic write policy shared by native and retained services."""

from flareward.resources.domain.builtins import BuiltinResourceDescriptor
from flareward.resources.domain.categories import ResourceVisibility
from flareward.resources.domain.models import Resource
from flareward.resources.errors import BuiltInWriteProtectedError, ResourceAccessDeniedError
from flareward.services.identity.scope import CallerScope


def require_visible(
    resource: Resource, descriptor: BuiltinResourceDescriptor | None, caller: CallerScope
) -> None:
    if caller.is_admin:
        return
    if descriptor is not None:
        if descriptor.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(resource.rid)
    elif caller.identity is not None and not caller.identity.owns(resource.identity):
        raise KeyError(resource.rid)


def require_custom_write(
    resource: Resource, descriptor: BuiltinResourceDescriptor | None, caller: CallerScope
) -> None:
    if caller.is_admin:
        return
    if descriptor is not None:
        raise BuiltInWriteProtectedError()
    if caller.identity is None or not caller.identity.owns(resource.identity):
        raise ResourceAccessDeniedError(resource.rid)
