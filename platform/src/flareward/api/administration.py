"""Human-only configuration and transparency endpoints on the canonical platform API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from flareward.api.dependencies import HttpServices, HumanPrincipal, get_services, human_principal
from flareward.services.administration.contracts import SettingsConflict, SettingsUnavailable
from flareward.services.administration.views import ConfigurationView
from flareward.services.identity.consent import ConsentUnavailable

router = APIRouter(prefix="/api", tags=["administration"])
type Human = Annotated[HumanPrincipal, Depends(human_principal)]
type Services = Annotated[HttpServices, Depends(get_services)]


class UpdateSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str = Field(min_length=1)
    values: dict[str, JsonValue]
    expected_revision: int = Field(ge=0)


@router.get("/administration/access")
async def access(principal: Human, services: Services) -> dict[str, bool]:
    allowed = services.configuration is not None and await services.configuration.allowed(
        principal.user
    )
    return {"is_admin": allowed}


@router.get("/administration/configuration", response_model=ConfigurationView)
async def configuration(principal: Human, services: Services) -> ConfigurationView:
    if services.configuration is None:
        raise HTTPException(503, "Configuration requires durable storage")
    try:
        return await services.configuration.read(principal.user)
    except PermissionError:
        raise HTTPException(403, "Administrator access is required") from None
    except SettingsUnavailable:
        raise HTTPException(503, "Configuration storage is unavailable") from None


@router.put("/administration/configuration")
async def update(
    request: UpdateSection, principal: Human, services: Services
) -> dict[str, JsonValue]:
    if services.configuration is None:
        raise HTTPException(503, "Configuration requires durable storage")
    try:
        record = await services.configuration.update(
            request.section, request.values, request.expected_revision, principal.user
        )
        return {"status": "success", "on_update_action": None, "revision": record.revision}
    except PermissionError:
        raise HTTPException(403, "Administrator access is required") from None
    except KeyError:
        raise HTTPException(404, "Configuration section not found") from None
    except SettingsConflict:
        raise HTTPException(409, "Configuration changed; reload before saving") from None
    except ValueError:
        raise HTTPException(422, "Invalid configuration section values") from None
    except SettingsUnavailable:
        raise HTTPException(503, "Configuration storage is unavailable") from None


@router.get("/consents/ai-transparency")
async def consent_status(principal: Human, services: Services) -> dict[str, JsonValue]:
    if services.consents is None:
        raise HTTPException(503, "Consent storage is not configured")
    try:
        return {
            "approved": await services.consents.accepted(principal.user),
            "username": principal.user.id,
        }
    except ConsentUnavailable:
        raise HTTPException(503, "Consent storage is unavailable") from None


@router.post("/consents/ai-transparency")
async def consent(principal: Human, services: Services) -> dict[str, JsonValue]:
    if services.consents is None:
        raise HTTPException(503, "Consent storage is not configured")
    try:
        await services.consents.accept(principal.user)
    except ConsentUnavailable:
        raise HTTPException(503, "Consent storage is unavailable") from None
    return {
        "status": "success",
        "message": "Consent recorded",
        "approved": True,
        "username": principal.user.id,
    }
