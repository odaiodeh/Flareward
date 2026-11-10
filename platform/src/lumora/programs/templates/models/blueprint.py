"""Portable template drafts; installed catalog schemas validate executable resources."""

from pydantic import BaseModel, ConfigDict, Field

from lumora.programs.templates.contracts import BlueprintExecutionSettings
from lumora.programs.templates.models.prompt_shortcuts import PromptShortcuts
from lumora.resources.domain.construction import BlueprintResource, StepDef


class TemplateConfiguration(BaseModel):
    """Retain authored fields without importing every optional integration SDK."""

    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)


class BlueprintDraft(BlueprintExecutionSettings):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    providers: list[BlueprintResource[TemplateConfiguration]] = Field(default_factory=list)
    llms: list[BlueprintResource[TemplateConfiguration]] = Field(default_factory=list)
    retrievers: list[BlueprintResource[TemplateConfiguration]] = Field(default_factory=list)
    tools: list[BlueprintResource[TemplateConfiguration]] = Field(default_factory=list)
    nodes: list[BlueprintResource[TemplateConfiguration]] = Field(default_factory=list)
    conditions: list[BlueprintResource[TemplateConfiguration]] = Field(default_factory=list)
    sandboxes: tuple[()] = ()
    plan: list[StepDef]
    name: str = "Untitled blueprint"
    description: str = ""
    prompt_shortcuts: PromptShortcuts | None = None
