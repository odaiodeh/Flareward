"""Explicit application-program registration, owned by the composition root."""

from dataclasses import dataclass

from pydantic import BaseModel

from mas.programs.ports import ApplicationProgram


@dataclass(frozen=True)
class ApplicationRegistration:
    key: str
    version: str
    config_schema: type[BaseModel]
    execute: ApplicationProgram


class ApplicationRegistry:
    def __init__(self) -> None:
        self._implementations: dict[tuple[str, str], ApplicationRegistration] = {}

    def register(self, registration: ApplicationRegistration) -> None:
        identity = registration.key, registration.version
        if identity in self._implementations:
            raise ValueError(f"Application program already registered: {identity}")
        self._implementations[identity] = registration

    def get(self, key: str, version: str) -> ApplicationRegistration:
        try:
            return self._implementations[key, version]
        except KeyError as error:
            raise ValueError(f"Application program is not installed: {key}@{version}") from error
