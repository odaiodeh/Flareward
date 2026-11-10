from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from lumora.programs.domain.metadata import StepMeta
from lumora.programs.graph.models.adjacency import AdjacentNodes
from lumora.programs.graph.topology.models import StepTopology


class StepContext(BaseModel):
    """Immutable context object injected into nodes / conditions at runtime."""

    uid: str
    metadata: StepMeta = Field(default_factory=StepMeta)
    adjacent_nodes: AdjacentNodes = Field(default_factory=AdjacentNodes.empty)
    branches: Dict[str, str] = Field(default_factory=dict)
    topology: StepTopology = Field(default_factory=StepTopology)

    model_config = ConfigDict(frozen=True)
