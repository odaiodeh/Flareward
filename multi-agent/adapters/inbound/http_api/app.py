"""FastAPI routers delegate to application services and own no execution loop."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from jsonschema import ValidationError as SchemaValidationError
from mas.application.collaboration.editing import EditLockUnavailable
from mas.application.elements.catalog.service import CatalogService
from mas.application.elements.exceptions import ElementInspectionError
from mas.application.sharing.notifications import ShareConflict, ShareStorageError
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.exceptions import (
    BlueprintConflictError,
    BlueprintDuplicateNameError,
    BlueprintStorageError,
    InvalidMetadataKeysError,
    PromptShortcutsValidationError,
)
from mas.blueprints.inspection import BlueprintInspectionService
from mas.blueprints.queries import BlueprintQueryService
from mas.core.identity import Identity
from mas.execution.models import ExecutionRecord, FailureKind, StartExecution
from mas.execution.ports import ExecutionError, ExecutionMissing
from mas.execution.service import ExecutionService
from mas.graph.analysis import BlueprintGraphAnalysisService, GraphAnalysisError
from mas.interactions.models import InteractionConflict
from mas.interactions.service import InteractionService
from mas.programs.blueprints import BlueprintProgramService
from mas.programs.models import ProgramDefinition, ProgramRef, ProgramRevision
from mas.programs.service import ProgramService
from mas.resources.authoring import ResourceAuthoringService
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceConflictError,
    ResourceDuplicateNameError,
    ResourceInUseError,
    ResourceStorageError,
)
from mas.resources.inspection import ResourceInspection
from mas.scheduling.programs import (
    ProgramScheduleConflict,
    ProgramScheduleError,
    ProgramScheduleService,
)
from mas.session.execution.blueprint_sessions import BlueprintSessionService
from mas.session.execution.program_sessions import ProgramSessionService
from mas.session.execution.queries import SessionQueryService
from mas.session.execution.session_store import SessionConflict
from pydantic import BaseModel, ConfigDict, JsonValue

from inbound.http_api.actions import router as actions_router
from inbound.http_api.authoring import router as authoring_router
from inbound.http_api.blueprint_inspection import router as blueprint_inspection_router
from inbound.http_api.blueprints import router as blueprints_router
from inbound.http_api.catalog import router as catalog_router
from inbound.http_api.dependencies import (
    Authenticator,
    HttpServices,
    ServicesFactory,
    authenticated,
    get_services,
)
from inbound.http_api.edit_locks import router as edit_locks_router
from inbound.http_api.graph_analysis import router as graph_analysis_router
from inbound.http_api.interactions import router as interactions_router
from inbound.http_api.resource_inspection import router as resource_inspection_router
from inbound.http_api.resources import router as resources_router
from inbound.http_api.schedules import router as schedules_router
from inbound.http_api.sessions import router as sessions_router
from inbound.http_api.shares import router as shares_router
from inbound.http_api.ui_blueprints import router as ui_blueprints_router
from inbound.http_api.ui_resources import router as ui_resources_router
from inbound.http_api.ui_session_streams import router as ui_session_streams_router
from inbound.http_api.ui_sessions import router as ui_sessions_router


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    data: JsonValue = None


def create_app(
    programs: ProgramService | None = None,
    executions: ExecutionService | None = None,
    authenticate: Authenticator | None = None,
    *,
    services_factory: ServicesFactory | None = None,
    sessions: ProgramSessionService | None = None,
    interactions: InteractionService | None = None,
    blueprints: BlueprintProgramService | None = None,
    authoring: BlueprintAuthoringService | None = None,
    resources: ResourceAuthoringService | None = None,
    inspection: ResourceInspection | None = None,
    blueprint_inspection: BlueprintInspectionService | None = None,
    graph_analysis: BlueprintGraphAnalysisService | None = None,
    schedules: ProgramScheduleService | None = None,
    catalog: CatalogService | None = None,
    blueprint_queries: BlueprintQueryService | None = None,
    blueprint_sessions: BlueprintSessionService | None = None,
    session_queries: SessionQueryService | None = None,
) -> FastAPI:
    """Resources are assembled inside lifespan, on the server's event loop."""
    if services_factory is None and (
        programs is None or executions is None or authenticate is None
    ):
        raise ValueError("Supply application services or a lifespan services factory")
    if services_factory is not None and any(
        value is not None
        for value in (
            programs,
            executions,
            authenticate,
            sessions,
            interactions,
            blueprints,
            authoring,
            resources,
            inspection,
            blueprint_inspection,
            graph_analysis,
            schedules,
            catalog,
            blueprint_queries,
            blueprint_sessions,
            session_queries,
        )
    ):
        raise ValueError("A services factory cannot be combined with prebuilt services")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if services_factory is not None:
            async with services_factory() as services:
                app.state.platform = services
                try:
                    yield
                finally:
                    app.state.platform = None
        else:
            try:
                yield
            finally:
                await executions.close()
                app.state.platform = None

    app = FastAPI(title="UnifAI Program Platform", lifespan=lifespan)
    if services_factory is None:
        app.state.platform = HttpServices(
            programs,
            executions,
            authenticate,
            sessions,
            interactions,
            blueprints,
            authoring,
            resources,
            inspection,
            blueprint_inspection,
            graph_analysis,
            schedules,
            catalog,
            blueprint_queries,
            blueprint_sessions,
            session_queries,
        )
    app.include_router(ui_sessions_router)
    app.include_router(ui_session_streams_router)
    app.include_router(sessions_router)
    app.include_router(interactions_router)
    app.include_router(blueprints_router)
    app.include_router(ui_blueprints_router)
    app.include_router(authoring_router)
    app.include_router(catalog_router)
    app.include_router(actions_router)
    app.include_router(shares_router)
    app.include_router(edit_locks_router)
    app.include_router(ui_resources_router)
    app.include_router(resources_router)
    app.include_router(resource_inspection_router)
    app.include_router(blueprint_inspection_router)
    app.include_router(graph_analysis_router)
    app.include_router(schedules_router)

    async def permission_error(request: Request, error: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Access denied"})

    async def missing_error(request: Request, error: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Resource not found"})

    async def invalid_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    app.add_exception_handler(PermissionError, permission_error)
    app.add_exception_handler(ResourceAccessDeniedError, permission_error)
    app.add_exception_handler(BuiltInWriteProtectedError, permission_error)
    app.add_exception_handler(KeyError, missing_error)
    app.add_exception_handler(ValueError, invalid_error)
    app.add_exception_handler(SchemaValidationError, invalid_error)
    app.add_exception_handler(InvalidMetadataKeysError, invalid_error)
    app.add_exception_handler(PromptShortcutsValidationError, invalid_error)

    async def request_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {key: item[key] for key in ("type", "loc", "msg")} for item in error.errors()
                ]
            },
        )

    app.add_exception_handler(RequestValidationError, request_validation_error)

    async def blueprint_storage_error(
        request: Request, error: BlueprintStorageError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    app.add_exception_handler(BlueprintStorageError, blueprint_storage_error)
    app.add_exception_handler(ResourceStorageError, blueprint_storage_error)
    app.add_exception_handler(ElementInspectionError, blueprint_storage_error)
    app.add_exception_handler(GraphAnalysisError, blueprint_storage_error)
    app.add_exception_handler(ProgramScheduleError, blueprint_storage_error)
    app.add_exception_handler(EditLockUnavailable, blueprint_storage_error)
    app.add_exception_handler(ShareStorageError, blueprint_storage_error)

    async def resource_in_use(request: Request, error: ResourceInUseError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Resource is referenced by other authoring documents"},
        )

    app.add_exception_handler(ResourceInUseError, resource_in_use)

    async def execution_error(request: Request, error: ExecutionError) -> JSONResponse:
        return JSONResponse(
            status_code=503 if error.failure.kind == FailureKind.INFRASTRUCTURE else 409,
            content={"detail": error.failure.model_dump(mode="json")},
        )

    app.add_exception_handler(ExecutionError, execution_error)
    app.add_exception_handler(ExecutionMissing, missing_error)

    async def session_conflict(request: Request, error: SessionConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    app.add_exception_handler(SessionConflict, session_conflict)
    app.add_exception_handler(InteractionConflict, session_conflict)
    app.add_exception_handler(BlueprintConflictError, session_conflict)
    app.add_exception_handler(BlueprintDuplicateNameError, session_conflict)
    app.add_exception_handler(ResourceConflictError, session_conflict)
    app.add_exception_handler(ResourceDuplicateNameError, session_conflict)
    app.add_exception_handler(ProgramScheduleConflict, session_conflict)
    app.add_exception_handler(ShareConflict, session_conflict)

    @app.get("/api/health/health")
    async def health(services: Annotated[HttpServices, Depends(get_services)]) -> dict[str, str]:
        return {"status": "ok"}

    @app.put("/api/programs/{program_id}", response_model=ProgramDefinition)
    async def save_program(
        program_id: str,
        definition: ProgramDefinition,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramDefinition:
        if program_id != definition.program_id:
            raise ValueError("Program path and body identities must match")
        return await services.programs.save(definition, caller)

    @app.post(
        "/api/programs/{program_id}/revisions", response_model=ProgramRevision, status_code=201
    )
    async def publish_program(
        program_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramRevision:
        return await services.programs.publish(program_id, caller)

    @app.get("/api/programs/{program_id}/revisions/{revision}", response_model=ProgramRevision)
    async def get_revision(
        program_id: str,
        revision: int,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramRevision:
        return await services.programs.revision(
            ProgramRef(program_id=program_id, revision=revision), caller
        )

    @app.post("/api/executions", response_model=ExecutionRecord, status_code=202)
    async def start_execution(
        request: StartExecution,
        http_request: Request,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ExecutionRecord:
        return await services.executions.start(
            request,
            caller,
            credential_user_id=getattr(http_request.state, "authenticated_user", ""),
        )

    @app.get("/api/executions/{execution_id}", response_model=ExecutionRecord)
    async def get_execution(
        execution_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ExecutionRecord:
        return await services.executions.refresh(execution_id, caller)

    @app.get("/api/executions/{execution_id}/result", response_model=ExecutionRecord)
    async def execution_result(
        execution_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ExecutionRecord:
        return await services.executions.result(execution_id, caller)

    @app.get("/api/executions/{execution_id}/children", response_model=list[ExecutionRecord])
    async def child_executions(
        execution_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> list[ExecutionRecord]:
        return await services.executions.children(execution_id, caller)

    @app.post("/api/executions/{execution_id}/cancel", status_code=202)
    async def cancel_execution(
        execution_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> dict[str, str]:
        await services.executions.cancel(execution_id, caller)
        return {"execution_id": execution_id, "status": "cancellation_requested"}

    @app.post("/api/executions/{execution_id}/messages", status_code=202)
    async def send_message(
        execution_id: str,
        message: MessageRequest,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> dict[str, str]:
        await services.executions.send(execution_id, message.name, message.data, caller)
        return {"status": "accepted"}

    @app.get("/api/executions/{execution_id}/events")
    async def stream_events(
        execution_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
        after_sequence: int = 0,
    ) -> StreamingResponse:
        await services.executions.get(execution_id, caller)

        async def stream() -> AsyncIterator[str]:
            async for event in services.executions.events(execution_id, caller, after_sequence):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
