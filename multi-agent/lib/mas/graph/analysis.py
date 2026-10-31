"""Authorize blueprint graph analysis without creating elements or engine runs."""

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.contracts import BlueprintData, BlueprintResolutionSource, ResolvedBlueprint
from mas.blueprints.resolution import resolve_blueprint
from mas.core.async_work import await_owned
from mas.core.identity import Identity
from mas.graph.plan_builder import PlanBuilder
from mas.graph.topology.path_algorithms import GraphAnalysisLimit
from mas.graph.validation.fix_models import FixSuggestion
from mas.graph.validation.models import ValidationReport, ValidationResult
from mas.graph.validation.service import GraphValidationService


class GraphAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_result: ValidationResult | ValidationReport
    fix_suggestions: list[FixSuggestion] = Field(default_factory=list)


class GraphAnalysisError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Graph analysis failed")


class BlueprintGraphAnalysisService:
    def __init__(
        self,
        authoring: BlueprintAuthoringService,
        source: BlueprintResolutionSource,
        elements: ElementRegistry,
        validation: GraphValidationService,
    ) -> None:
        self._authoring, self._source = authoring, source
        self._plans, self._validation = PlanBuilder(elements), validation

    def validation_names(self) -> list[str]:
        return self._validation.get_validation_names()

    async def analyze(
        self,
        caller: Identity,
        *,
        blueprint_id: str | None = None,
        spec: BlueprintData | None = None,
        validator: str | None = None,
    ) -> GraphAnalysis:
        if validator is not None and validator not in self.validation_names():
            raise ValueError("Unknown graph validator")
        resolved = await resolve_blueprint(
            self._authoring, self._source, caller, blueprint_id=blueprint_id, spec=spec
        )
        if resolved.missing:
            raise KeyError("Blueprint resource not found")
        # Topology/path analysis can be CPU-intensive. Own that work through cancellation.
        return await await_owned(asyncio.to_thread(self._analyze, resolved.blueprint, validator))

    def _analyze(self, blueprint: ResolvedBlueprint, validator: str | None) -> GraphAnalysis:
        try:
            plan = self._plans.build(blueprint)
        except ValueError, KeyError:
            raise ValueError("Invalid blueprint graph") from None
        if len(plan) > 256:
            raise GraphAnalysisLimit()
        try:
            result, suggestions = self._validation.validate_and_suggest(plan, validator)
            return GraphAnalysis(validation_result=result, fix_suggestions=suggestions)
        except GraphAnalysisLimit:
            raise
        except Exception:
            raise GraphAnalysisError() from None
