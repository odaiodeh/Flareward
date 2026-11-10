"""Installed plugin contributions; configuration and execution remain separate lifecycles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginDefinition:
    key: str
    version: str
    elements: tuple[str, ...] = ()
    programs: tuple[str, ...] = ()
    graph_validators: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.version.strip():
            raise ValueError("Plugins require an identity and implementation version")
        if len(set(self.elements)) != len(self.elements) or len(set(self.programs)) != len(
            self.programs
        ):
            raise ValueError("Plugin contribution modules must be unique")
