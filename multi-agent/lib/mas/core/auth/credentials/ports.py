"""
Auth-layer storage ports — protocol-agnostic persistence contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .models import ClientConfig, StoredCredential


class CipherError(ValueError):
    """An encoded credential cannot be decoded with the configured key."""


class TokenCipher(Protocol):
    """Protect values; decrypt preserves plaintext and raises CipherError on invalid ciphertext."""

    def encrypt(self, value: str | None) -> str | None: ...
    def decrypt(self, value: str | None) -> str | None: ...


class CredentialStore(ABC):
    """Persist and retrieve :class:`StoredCredential` objects."""

    @abstractmethod
    def upsert(self, credential: StoredCredential) -> None: ...

    @abstractmethod
    def find_by_server(
        self,
        user_id: str,
        server_identifier: str,
        scheme_type: str = "",
    ) -> StoredCredential | None: ...

    @abstractmethod
    def delete(self, user_id: str, server_identifier: str) -> None: ...

    @abstractmethod
    def update_status(self, user_id: str, server_identifier: str, status: str) -> None: ...


class ServerConfigStore(ABC):
    """Persist and retrieve :class:`ClientConfig` objects."""

    @abstractmethod
    def find_by_server(self, user_id: str, server_identifier: str) -> ClientConfig | None: ...

    @abstractmethod
    def save(self, user_id: str, config: ClientConfig) -> None: ...

    @abstractmethod
    def list_by_category(self, category: str) -> list[ClientConfig]: ...
