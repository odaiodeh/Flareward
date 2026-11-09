"""Human transparency consent is distinct from workflow approval and authority."""

from typing import Protocol

from flareward.services.identity.domain import Identity

CONSENT = "ai-transparency@1"


class ConsentUnavailable(RuntimeError):
    pass


class ConsentRepository(Protocol):
    async def accepted(self, user: str, version: str) -> bool: ...
    async def accept(self, user: str, version: str) -> None: ...


class ConsentService:
    def __init__(self, repository: ConsentRepository) -> None:
        self._repository = repository

    @staticmethod
    def _user(user: Identity) -> str:
        if not user.is_user or not user.id:
            raise PermissionError("Consent requires an authenticated human")
        return user.id

    async def accepted(self, user: Identity) -> bool:
        return await self._repository.accepted(self._user(user), CONSENT)

    async def accept(self, user: Identity) -> None:
        await self._repository.accept(self._user(user), CONSENT)
