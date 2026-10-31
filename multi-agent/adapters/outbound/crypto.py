"""Fernet field format compatible with the existing library and credential store."""

from cryptography.fernet import Fernet, InvalidToken
from mas.core.auth.credentials.ports import CipherError


class FieldCipher:
    def __init__(self, key: str) -> None:
        self._cipher = Fernet(key.encode())

    def encrypt(self, value: str | None) -> str | None:
        return self._cipher.encrypt(value.encode()).decode() if value else value

    def decrypt(self, value: str | None) -> str | None:
        if not value or not value.startswith("gAAAAAB"):
            return value
        try:
            return self._cipher.decrypt(value.encode()).decode()
        except InvalidToken:
            raise CipherError("Encrypted credential cannot be decoded") from None
