"""Existing editor action routes delegate typed discovery/execution to the application."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from flareward.api.dependencies import authenticated, get_actions
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.actions.contracts import ActionContext, ActionMetadata, ActionType
from flareward.services.actions.service import ActionExecutionFailed, ActionMissing, ActionsService
from flareward.services.identity.domain import Identity

router = APIRouter(prefix="/api/actions", tags=["authoring actions"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[ActionsService, Depends(get_actions)]


class Filters(BaseModel):
    category: ResourceCategory | None = None
    type: str | None = None
    action_type: ActionType | None = None
    tags: list[str] | None = None


class ActionList(BaseModel):
    actions: list[ActionMetadata]
    total_actions: int
    filters_applied: Filters


class ExecuteAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: str = Field(min_length=1)
    input_data: dict[str, JsonValue] = Field(default_factory=dict, alias="inputData")
    context: dict[str, JsonValue] = Field(default_factory=dict)
    user_id: str | None = Field(default=None, alias="userId")
    team_id: str | None = Field(default=None, alias="teamId")


@router.get("/actions.list", response_model=ActionList)
async def list_actions(
    caller: Caller,
    service: Service,
    category: ResourceCategory | None = None,
    type_key: Annotated[str | None, Query(alias="type")] = None,
    action_type: Annotated[ActionType | None, Query(alias="actionType")] = None,
    tags: Annotated[list[str] | None, Query()] = None,
) -> ActionList:
    descriptions = service.get_actions_metadata(
        action_type=action_type,
        tags=set(tags) if tags else None,
        category=category.value if category else None,
        element_type=type_key,
    )
    return ActionList(
        actions=descriptions,
        total_actions=len(descriptions),
        filters_applied=Filters(
            category=category, type=type_key, action_type=action_type, tags=tags
        ),
    )


@router.post("/action.execute")
async def execute_action(
    body: ExecuteAction, request: Request, caller: Caller, service: Service
) -> dict[str, JsonValue]:
    try:
        result = await service.execute(
            body.uid,
            body.input_data,
            ActionContext(
                owner=caller,
                credential_user_id=request.state.authenticated_user,
                data=body.context,
            ),
        )
    except ActionMissing:
        raise HTTPException(status_code=404, detail="Action not found") from None
    except ActionExecutionFailed:
        raise HTTPException(status_code=502, detail="Action execution failed") from None
    return result.model_dump(mode="json")
