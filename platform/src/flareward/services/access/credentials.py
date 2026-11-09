"""Opaque purpose-separated credentials; scopes and authorization remain with each service."""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from pydantic import SecretStr

from flareward.services.identity.domain import Identity


class WorkflowCredentialUnavailable(RuntimeError):
    """A private workflow credential source cannot currently resolve material."""


class WorkflowCredentialSource(Protocol):
    async def resolve(self, purpose: str, owner: Identity, root_execution_id: str) -> SecretStr: ...


@dataclass(frozen=True)
class IssuedCredential:
    identifier: str
    secret: SecretStr
    sha256: str = field(repr=False)


class OpaqueCredentials:
    def __init__(self, purpose: str) -> None:
        self._purpose = purpose
        self._pattern = re.compile(re.escape(purpose) + r"\.([a-f0-9]{32})\.[A-Za-z0-9_-]{43}")

    def issue(self) -> IssuedCredential:
        return self.issue_for(uuid4().hex)

    def issue_for(self, identifier: str) -> IssuedCredential:
        if re.fullmatch(r"[a-f0-9]{32}", identifier) is None:
            raise ValueError("Credential identifier is invalid")
        secret = f"{self._purpose}.{identifier}.{secrets.token_urlsafe(32)}"
        return IssuedCredential(identifier, SecretStr(secret), self.digest(secret))

    def identify(self, secret: str) -> str | None:
        match = self._pattern.fullmatch(secret)
        return match[1] if match else None

    @staticmethod
    def digest(secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()

    def matches(self, secret: str, digest: str) -> bool:
        return hmac.compare_digest(self.digest(secret), digest)
