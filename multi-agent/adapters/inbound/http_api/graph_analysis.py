"""Native graph analysis plus the retained YAML validation transport contract."""

from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from mas.core.identity import Identity
from mas.graph.analysis import BlueprintGraphAnalysisService, GraphAnalysis
from pydantic import BaseModel, ConfigDict, Field

from inbound.blueprints.files import parse_blueprint
from inbound.http_api.blueprint_inspection import DraftSelection
from inbound.http_api.dependencies import authenticated, get_graph_analysis

router = APIRouter(tags=["graph validation"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[BlueprintGraphAnalysisService, Depends(get_graph_analysis)]


class GraphSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator: str | None = Field(default=None, min_length=1)


class DraftGraphSelection(DraftSelection, GraphSelection):
    pass


class LegacyGraphCheck(StrEnum):
    ALL = "all"
    CHANNELS = "channels"
    DEPENDENCIES = "dependencies"
    CYCLES = "cycles"
    ORPHANS = "orphans"
    REQUIRED_NODES = "required_nodes"


_LEGACY_CHECKS = {
    LegacyGraphCheck.ALL: None,
    LegacyGraphCheck.CHANNELS: "channel",
    LegacyGraphCheck.DEPENDENCIES: "dependency",
    LegacyGraphCheck.CYCLES: "cycle",
    LegacyGraphCheck.ORPHANS: "orphan",
    LegacyGraphCheck.REQUIRED_NODES: "required_nodes",
}


@router.get("/api/graph/validation/names")
@router.get("/api/graph/validation/names.get", include_in_schema=False)
async def names(caller: Caller, service: Service) -> dict[str, list[str]]:
    return {"validation_names": service.validation_names()}


@router.post("/api/blueprints/draft/graph-validation", response_model=GraphAnalysis)
async def analyze_draft(
    body: DraftGraphSelection, caller: Caller, service: Service
) -> GraphAnalysis:
    return await service.analyze(caller, spec=body.spec, validator=body.validator)


@router.post("/api/blueprints/{blueprint_id}/graph-validation", response_model=GraphAnalysis)
async def analyze_saved(
    blueprint_id: str, body: GraphSelection, caller: Caller, service: Service
) -> GraphAnalysis:
    return await service.analyze(caller, blueprint_id=blueprint_id, validator=body.validator)


@router.post("/api/graph/validation/{check}.validate", response_model=GraphAnalysis)
async def analyze_yaml(
    check: LegacyGraphCheck, request: Request, caller: Caller, service: Service
) -> GraphAnalysis:
    return await service.analyze(
        caller, spec=parse_blueprint(await request.body()), validator=_LEGACY_CHECKS[check]
    )
