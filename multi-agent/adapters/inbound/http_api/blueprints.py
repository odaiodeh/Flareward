"""Native blueprint import delegates authorization, resolution, and program protection."""

from typing import Annotated

from fastapi import APIRouter, Depends
from mas.core.identity import Identity
from mas.programs.blueprints import BlueprintProgramService
from mas.programs.models import ProgramDefinition
from pydantic import BaseModel, ConfigDict, Field

from inbound.http_api.dependencies import authenticated, get_blueprints

router = APIRouter(prefix="/api/programs", tags=["blueprints"])


class BlueprintImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blueprint_id: str = Field(min_length=1)
    execution_profile: str | None = Field(default=None, min_length=1)


@router.put("/{program_id}/blueprint", response_model=ProgramDefinition)
async def import_blueprint(
    program_id: str,
    request: BlueprintImport,
    caller: Annotated[Identity, Depends(authenticated)],
    service: Annotated[BlueprintProgramService, Depends(get_blueprints)],
) -> ProgramDefinition:
    return await service.save(
        request.blueprint_id, program_id, caller, execution_profile=request.execution_profile
    )
