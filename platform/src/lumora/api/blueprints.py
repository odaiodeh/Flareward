"""Native blueprint import delegates authorization, resolution, and program protection."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from lumora.api.dependencies import authenticated, get_blueprints
from lumora.programs.authoring import ProgramDraft
from lumora.programs.blueprints import BlueprintProgramService
from lumora.services.identity.domain import Identity

router = APIRouter(prefix="/api/programs", tags=["blueprints"])


class BlueprintImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blueprint_id: str = Field(min_length=1)
    execution_profile: str | None = Field(default=None, min_length=1)


@router.put("/{program_id}/blueprint", response_model=ProgramDraft)
async def import_blueprint(
    program_id: str,
    request: BlueprintImport,
    caller: Annotated[Identity, Depends(authenticated)],
    service: Annotated[BlueprintProgramService, Depends(get_blueprints)],
) -> ProgramDraft:
    return await service.save(
        request.blueprint_id, program_id, caller, execution_profile=request.execution_profile
    )
