"""Build authoring and resolution contracts from the installed element catalog."""

from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, create_model, model_validator

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.blueprints.contracts import BlueprintExecutionSettings
from mas.blueprints.models.prompt_shortcuts import PromptShortcuts
from mas.core.enums import ResourceCategory
from mas.core.ref.models import Ref
from mas.core.resource_models import BlueprintResource, ResourceSpec, StepDef


class _CatalogResource(BlueprintResource[BaseModel]):
    rid: Ref = Field(json_schema_extra={"pattern": r"^\$ref:.+"})
    config: None = None

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if not self.rid.is_external_ref() or not self.rid.ref:
            raise ValueError("A catalog resource requires a nonempty external reference")
        return self


class _InlineResource[T: BaseModel](BlueprintResource[T]):
    rid: Ref = Field(json_schema_extra={"pattern": r"^(?!\$ref:).+"})
    name: str
    config: SerializeAsAny[T]

    @model_validator(mode="after")
    def require_inline(self) -> Self:
        if self.rid.is_external_ref() or not self.rid.ref:
            raise ValueError("An inline resource requires a nonempty local identity")
        return self


class _BlueprintMetadata(BlueprintExecutionSettings):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    plan: list[StepDef]
    name: str = "Untitled blueprint"
    description: str = ""

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        for step in self.plan:
            for selection in (step.execution, step.condition_execution):
                if selection is not None and selection.environment is not None:
                    if selection.environment not in self.environments:
                        raise ValueError("Step placement references an undeclared environment")
        for category in ResourceCategory:
            for resource in getattr(self, category.value):
                if resource.execution is not None:
                    resource.execution.validate_category(category)
        return self


class _DraftMetadata(_BlueprintMetadata):
    prompt_shortcuts: PromptShortcuts | None = None


@dataclass(frozen=True)
class BlueprintSchemas:
    draft: type[BaseModel]
    resolved: type[BaseModel]


def blueprint_schemas(elements: ElementRegistry) -> BlueprintSchemas:
    """Freeze the registered schemas once, after catalog registration at startup.

    Dispatch by category and the resource's explicit type key. Configuration models
    need no internal type discriminator and retain typed references and secret hints.
    """
    draft_fields, resolved_fields = {}, {}
    catalog = elements.get_categories_map()
    for category in ResourceCategory:
        if category == ResourceCategory.SANDBOX:
            retired = (tuple[()], Field(default=(), description="Retired; use execution profiles"))
            draft_fields[category.value] = retired
            resolved_fields[category.value] = retired
            continue
        inline, resolved = [], []
        for key, specification in sorted(catalog.get(category, {}).items()):
            schema = specification.config_schema
            inline.append(
                create_model(
                    f"Inline_{category.value}_{key}",
                    __base__=_InlineResource[schema],
                    type=(Literal[key], ...),
                )
            )
            resolved.append(
                create_model(
                    f"Resolved_{category.value}_{key}",
                    __base__=ResourceSpec[schema],
                    type=(Literal[key], ...),
                )
            )
        resource_type = (
            _CatalogResource | Annotated[reduce(or_, inline), Field(discriminator="type")]
            if inline
            else _CatalogResource
        )
        draft_fields[category.value] = (list[resource_type], Field(default_factory=list))
        resolved_fields[category.value] = (
            (
                list[Annotated[reduce(or_, resolved), Field(discriminator="type")]],
                Field(default_factory=list),
            )
            if resolved
            else (tuple[()], ())
        )
    return BlueprintSchemas(
        draft=create_model("RegisteredBlueprintDraft", __base__=_DraftMetadata, **draft_fields),
        resolved=create_model(
            "RegisteredBlueprintSpec", __base__=_BlueprintMetadata, **resolved_fields
        ),
    )
