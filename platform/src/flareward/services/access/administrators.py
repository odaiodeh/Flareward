"""Human administrator policy uses an authoritative directory and explicit bootstrap users."""

from typing import Protocol

from flareward.services.identity.domain import Identity


class AdministratorAccessUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Administrator authority is unavailable")


class AdministratorDirectory(Protocol):
    async def usernames(self) -> tuple[str, ...] | None:
        """None means no persisted policy; an empty policy explicitly denies everyone."""
        ...


class AdministratorAccess(Protocol):
    async def allowed(self, user: Identity) -> bool: ...


class AdministratorPolicy:
    def __init__(
        self, directory: AdministratorDirectory, bootstrap_users: tuple[str, ...] = ()
    ) -> None:
        self._directory = directory
        self._bootstrap = frozenset(user.casefold() for user in bootstrap_users)

    async def allowed(self, user: Identity) -> bool:
        if not user.is_user or not user.id:
            return False
        persisted = await self._directory.usernames()
        allowed = (
            self._bootstrap
            if persisted is None
            else frozenset(name.casefold() for name in persisted)
        )
        return user.id.casefold() in allowed
