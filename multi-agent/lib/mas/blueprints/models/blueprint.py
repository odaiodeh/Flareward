"""Blueprint authoring and legacy portable contracts, preserving category validation."""

from typing import Any

from pydantic import ConfigDict, Field

from mas.blueprints.contracts import BlueprintDocument as BlueprintDocument
from mas.blueprints.contracts import BlueprintExecutionSettings
from mas.blueprints.contracts import BlueprintSummary as BlueprintSummary
from mas.blueprints.models.prompt_shortcuts import PromptShortcuts
from mas.core.resource_models import BlueprintExecutionStats as BlueprintExecutionStats
from mas.core.resource_models import BlueprintResource, ResourceSpec, StepDef
from mas.core.resource_models import StepMeta as StepMeta
from mas.elements.conditions.types import ConditionSpec
from mas.elements.llms.types import LLMsSpec
from mas.elements.nodes.types import NodeSpec
from mas.elements.providers.types import ProviderSpec
from mas.elements.retrievers.types import RetrieversSpec
from mas.elements.tools.types import ToolsSpec


class BlueprintDraft(BlueprintExecutionSettings):
    """UI-authorable document containing inline resources and catalog references."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    providers: list[BlueprintResource[ProviderSpec]] = Field(default_factory=list)
    llms: list[BlueprintResource[LLMsSpec]] = Field(default_factory=list)
    retrievers: list[BlueprintResource[RetrieversSpec]] = Field(default_factory=list)
    tools: list[BlueprintResource[ToolsSpec]] = Field(default_factory=list)
    nodes: list[BlueprintResource[NodeSpec]] = Field(default_factory=list)
    conditions: list[BlueprintResource[ConditionSpec]] = Field(default_factory=list)
    sandboxes: tuple[()] = ()
    plan: list[StepDef]
    name: str = "Untitled blueprint"
    description: str = ""
    prompt_shortcuts: PromptShortcuts | None = None

    @classmethod
    def from_stored_dict(cls, spec_dict: dict[str, Any]) -> BlueprintDraft:
        """Ignore retired top-level fields when reading our own older documents.

        Newly submitted drafts remain strict so client mistakes are reported.
        """
        return cls.model_validate(
            {key: value for key, value in spec_dict.items() if key in cls.model_fields}
        )


class BlueprintSpec(BlueprintExecutionSettings):
    """Resolved blueprint retaining existing concrete integration schemas."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    providers: list[ResourceSpec[ProviderSpec]]
    llms: list[ResourceSpec[LLMsSpec]]
    retrievers: list[ResourceSpec[RetrieversSpec]]
    tools: list[ResourceSpec[ToolsSpec]]
    nodes: list[ResourceSpec[NodeSpec]]
    conditions: list[ResourceSpec[ConditionSpec]] = Field(default_factory=list)
    sandboxes: tuple[()] = ()
    plan: list[StepDef]
    name: str
    description: str
