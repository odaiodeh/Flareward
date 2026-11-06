from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from mas.domain.metadata import StepMeta

from ..topology.models import StepTopology
from .adjacency import AdjacentNodes


class StepContext(BaseModel):
    """Immutable context object injected into nodes / conditions at runtime."""

    uid: str
    metadata: StepMeta = Field(default_factory=StepMeta)
    adjacent_nodes: AdjacentNodes = Field(default_factory=AdjacentNodes.empty)
    branches: Dict[str, str] = Field(default_factory=dict)
    topology: StepTopology = Field(default_factory=StepTopology)

    model_config = ConfigDict(frozen=True)
