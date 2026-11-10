"""Runtime element data owned by a construction scope."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from lumora.elements.specification import BaseElementSpec
from lumora.resources.domain.construction import ResourceSpec


@dataclass(frozen=True)
class RuntimeElement:
    """Complete runtime element: instance + spec + resource_spec."""

    instance: Any
    spec: type[BaseElementSpec]
    resource_spec: ResourceSpec

    @property
    def config(self) -> BaseModel:
        """Get config from resource_spec."""
        return self.resource_spec.config
