from lumora.api.administration import router as administration_router

"""FastAPI routers delegate to application services and own no execution loop."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from jsonschema import ValidationError as SchemaValidationError
from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.api.actions import router as actions_router
from lumora.api.artifact_access import router as artifact_access_router
from lumora.api.artifacts import router as artifacts_router
from lumora.api.authoring import router as authoring_router
from lumora.api.blueprint_inspection import router as blueprint_inspection_router
from lumora.api.blueprints import router as blueprints_router
from lumora.api.builtin_administration import router as builtin_administration_router
from lumora.api.catalog import router as catalog_router
from lumora.api.check_runs import router as check_runs_router
from lumora.api.curated_inspection import router as curated_inspection_router
from lumora.api.dependencies import (
    Authenticator,
    HttpServices,
    ServicesFactory,
    authenticated,
    get_services,
    human_principal,
)
from lumora.api.edit_locks import router as edit_locks_router
from lumora.api.event_sources import router as event_sources_router
from lumora.api.graph_analysis import router as graph_analysis_router
from lumora.api.interactions import router as interactions_router
from lumora.api.reporting import router as reporting_router
from lumora.api.resource_inspection import router as resource_inspection_router
from lumora.api.resources import router as resources_router
from lumora.api.reviews import router as reviews_router
from lumora.api.schedules import router as schedules_router
from lumora.api.sessions import router as sessions_router
from lumora.api.shares import router as shares_router
from lumora.api.ui_blueprints import router as ui_blueprints_router
from lumora.api.ui_resources import router as ui_resources_router
from lumora.api.ui_session_streams import router as ui_session_streams_router
from lumora.api.ui_sessions import router as ui_sessions_router
from lumora.api.verification_access import router as verification_access_router
from lumora.api.verification_auth import EvidenceAuthenticator
from lumora.api.verifications import router as verifications_router
from lumora.elements.catalog.service import CatalogService
from lumora.elements.construction.snapshots import (
    ResourceSnapshotConflict,
    ResourceSnapshotsUnavailable,
)
from lumora.elements.exceptions import ElementInspectionError
from lumora.executions.domain.models import ExecutionRecord, FailureKind
from lumora.executions.events import EventSourceConflict, EventSourceUnavailable
from lumora.executions.models import StartExecution
from lumora.executions.ports import (
    ExecutionError,
    ExecutionMissing,
    ExecutionRequestConflict,
)
from lumora.executions.service import ExecutionService
from lumora.programs.authoring import (
    ObservedProgramVersion,
    ProgramConflict,
    ProgramDraft,
    ProgramPage,
    ProgramStorageError,
    ProgramValidation,
    RevisionPage,
    SaveProgramDraft,
)
from lumora.programs.blueprints import BlueprintProgramService
from lumora.programs.domain.models import ProgramRef, ProgramRevision
from lumora.programs.graph.analysis import BlueprintGraphAnalysisService, GraphAnalysisError
from lumora.programs.service import ProgramService
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.exceptions import (
    BlueprintConflictError,
    BlueprintDuplicateNameError,
    BlueprintStorageError,
    InvalidMetadataKeysError,
    PromptShortcutsValidationError,
)
from lumora.programs.templates.inspection import BlueprintInspectionService
from lumora.programs.templates.queries import BlueprintQueryService
from lumora.resources.authoring import ResourceAuthoringService
from lumora.resources.errors import (
    BuiltinDependentsPublicError,
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceConflictError,
    ResourceDuplicateNameError,
    ResourceInUseError,
    ResourceLockedError,
    ResourceStorageError,
)
from lumora.resources.inspection import ResourceInspectionService
from lumora.services.access.administrators import AdministratorAccessUnavailable
from lumora.services.access.credentials import WorkflowCredentialUnavailable
from lumora.services.access.executions import ExecutionAccessUnavailable
from lumora.services.access.issuance import (
    CredentialIssuanceConflict,
)
from lumora.services.artifacts.access import ArtifactAccessService
from lumora.services.artifacts.ports import (
    ArtifactConflict,
    ArtifactLimitExceeded,
    ArtifactMissing,
    ArtifactStorageError,
)
from lumora.services.artifacts.service import ArtifactService
from lumora.services.collaboration.editing import EditLockUnavailable
from lumora.services.identity.domain import Identity
from lumora.services.interactions.models import InteractionConflict
from lumora.services.interactions.service import InteractionService
from lumora.services.reporting.service import ReportingUnavailable
from lumora.services.reviews.access import ReviewAccessService
from lumora.services.reviews.domain.models import REVIEW_MESSAGE_PREFIX
from lumora.services.reviews.ports import (
    ReviewConflict,
    ReviewMissing,
    ReviewStorageError,
    ReviewUnavailable,
)
from lumora.services.reviews.service import ReviewService
from lumora.services.scheduling.programs import (
    ProgramScheduleConflict,
    ProgramScheduleError,
    ProgramScheduleService,
)
from lumora.services.sessions.execution.blueprint_sessions import BlueprintSessionService
from lumora.services.sessions.execution.program_sessions import ProgramSessionService
from lumora.services.sessions.execution.queries import SessionQueryService
from lumora.services.sessions.execution.session_store import SessionConflict
from lumora.services.sharing.notifications import ShareConflict, ShareStorageError
from lumora.services.verification.access import VerificationAccessService
from lumora.services.verification.check_ports import CheckProviderUnavailable
from lumora.services.verification.check_service import CheckRunService
from lumora.services.verification.ports import (
    VerificationConflict,
    VerificationMissing,
    VerificationStorageError,
)
from lumora.services.verification.service import VerificationService


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
    inspection: ResourceInspectionService | None = None,
    blueprint_inspection: BlueprintInspectionService | None = None,
    graph_analysis: BlueprintGraphAnalysisService | None = None,
    schedules: ProgramScheduleService | None = None,
    catalog: CatalogService | None = None,
    blueprint_queries: BlueprintQueryService | None = None,
    blueprint_sessions: BlueprintSessionService | None = None,
    session_queries: SessionQueryService | None = None,
    artifacts: ArtifactService | None = None,
    artifact_access: ArtifactAccessService | None = None,
    verifications: VerificationService | None = None,
    authenticate_verifier: EvidenceAuthenticator | None = None,
    verification_access: VerificationAccessService | None = None,
    check_runs: CheckRunService | None = None,
    reviews: ReviewService | None = None,
    review_access: ReviewAccessService | None = None,
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
            artifacts,
            artifact_access,
            verifications,
            authenticate_verifier,
            verification_access,
            check_runs,
            reviews,
            review_access,
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
            assert executions is not None
            try:
                yield
            finally:
                await executions.close()
                app.state.platform = None

    app = FastAPI(title="Lumora Program Platform", lifespan=lifespan)
    if services_factory is None:
        assert programs is not None and executions is not None and authenticate is not None
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
            artifacts=artifacts,
            artifact_access=artifact_access,
            verifications=verifications,
            authenticate_verifier=authenticate_verifier,
            verification_access=verification_access,
            check_runs=check_runs,
            reviews=reviews,
            review_access=review_access,
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
    app.include_router(artifacts_router)
    app.include_router(artifact_access_router)
    app.include_router(verifications_router)
    app.include_router(verification_access_router)
    app.include_router(check_runs_router)
    app.include_router(reviews_router)
    app.include_router(reporting_router)
    app.include_router(builtin_administration_router)
    app.include_router(curated_inspection_router)
    app.include_router(shares_router)
    app.include_router(administration_router)
    app.include_router(edit_locks_router)
    app.include_router(ui_resources_router)
    app.include_router(resources_router)
    app.include_router(resource_inspection_router)
    app.include_router(blueprint_inspection_router)
    app.include_router(graph_analysis_router)
    app.include_router(schedules_router)
    app.include_router(event_sources_router)

    async def permission_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Access denied"})

    async def missing_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Resource not found"})

    async def invalid_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    app.add_exception_handler(PermissionError, permission_error)
    app.add_exception_handler(ResourceAccessDeniedError, permission_error)
    app.add_exception_handler(BuiltInWriteProtectedError, permission_error)
    app.add_exception_handler(KeyError, missing_error)
    app.add_exception_handler(ArtifactMissing, missing_error)
    app.add_exception_handler(VerificationMissing, missing_error)
    app.add_exception_handler(ReviewMissing, missing_error)
    app.add_exception_handler(ValueError, invalid_error)
    app.add_exception_handler(SchemaValidationError, invalid_error)
    app.add_exception_handler(InvalidMetadataKeysError, invalid_error)
    app.add_exception_handler(PromptShortcutsValidationError, invalid_error)

    async def request_validation_error(request: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, RequestValidationError)
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {key: item[key] for key in ("type", "loc", "msg")} for item in error.errors()
                ]
            },
        )

    app.add_exception_handler(RequestValidationError, request_validation_error)

    async def storage_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    app.add_exception_handler(BlueprintStorageError, storage_error)
    app.add_exception_handler(ResourceStorageError, storage_error)
    app.add_exception_handler(ElementInspectionError, storage_error)
    app.add_exception_handler(ArtifactStorageError, storage_error)
    app.add_exception_handler(VerificationStorageError, storage_error)
    app.add_exception_handler(ReviewStorageError, storage_error)
    app.add_exception_handler(ProgramStorageError, storage_error)
    app.add_exception_handler(ResourceSnapshotsUnavailable, storage_error)
    app.add_exception_handler(ReviewUnavailable, storage_error)
    app.add_exception_handler(CheckProviderUnavailable, storage_error)
    app.add_exception_handler(ExecutionAccessUnavailable, storage_error)
    app.add_exception_handler(WorkflowCredentialUnavailable, storage_error)
    app.add_exception_handler(ReportingUnavailable, storage_error)
    app.add_exception_handler(AdministratorAccessUnavailable, storage_error)
    app.add_exception_handler(EventSourceUnavailable, storage_error)

    async def artifact_limit_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=413, content={"detail": str(error)})

    app.add_exception_handler(ArtifactLimitExceeded, artifact_limit_error)
    app.add_exception_handler(GraphAnalysisError, storage_error)
    app.add_exception_handler(ProgramScheduleError, storage_error)
    app.add_exception_handler(EditLockUnavailable, storage_error)
    app.add_exception_handler(ShareStorageError, storage_error)

    async def resource_in_use(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Resource is referenced by other authoring documents"},
        )

    app.add_exception_handler(ResourceInUseError, resource_in_use)
    app.add_exception_handler(BuiltinDependentsPublicError, resource_in_use)

    async def execution_error(request: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, ExecutionError)
        return JSONResponse(
            status_code=503 if error.failure.kind == FailureKind.INFRASTRUCTURE else 409,
            content={"detail": error.failure.model_dump(mode="json")},
        )

    app.add_exception_handler(ExecutionError, execution_error)
    app.add_exception_handler(ExecutionMissing, missing_error)

    async def conflict_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    app.add_exception_handler(SessionConflict, conflict_error)
    app.add_exception_handler(InteractionConflict, conflict_error)
    app.add_exception_handler(BlueprintConflictError, conflict_error)
    app.add_exception_handler(BlueprintDuplicateNameError, conflict_error)
    app.add_exception_handler(ResourceConflictError, conflict_error)
    app.add_exception_handler(ResourceLockedError, conflict_error)
    app.add_exception_handler(ResourceDuplicateNameError, conflict_error)
    app.add_exception_handler(ProgramScheduleConflict, conflict_error)
    app.add_exception_handler(ShareConflict, conflict_error)
    app.add_exception_handler(ArtifactConflict, conflict_error)
    app.add_exception_handler(VerificationConflict, conflict_error)
    app.add_exception_handler(ReviewConflict, conflict_error)
    app.add_exception_handler(CredentialIssuanceConflict, conflict_error)
    app.add_exception_handler(ExecutionRequestConflict, conflict_error)
    app.add_exception_handler(ProgramConflict, conflict_error)
    app.add_exception_handler(EventSourceConflict, conflict_error)
    app.add_exception_handler(ResourceSnapshotConflict, conflict_error)

    @app.get("/api/health/health")
    async def health(services: Annotated[HttpServices, Depends(get_services)]) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/programs", response_model=ProgramPage)
    async def list_programs(
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
        after: str = "",
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> ProgramPage:
        return await services.programs.list(caller, after=after, limit=limit)

    @app.get("/api/programs/{program_id}", response_model=ProgramDraft)
    async def get_program_draft(
        program_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramDraft:
        return await services.programs.draft(program_id, caller)

    @app.put("/api/programs/{program_id}", response_model=ProgramDraft)
    async def save_program(
        program_id: str,
        command: SaveProgramDraft,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramDraft:
        definition = command.definition
        if program_id != definition.program_id:
            raise ValueError("Program path and body identities must match")
        return await services.programs.save(
            definition,
            caller,
            expected_version=command.expected_version,
            presentation=command.presentation,
            resource_selections=command.resource_selections,
        )

    @app.get("/api/programs/{program_id}/revisions", response_model=RevisionPage)
    async def list_program_revisions(
        program_id: str,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
        before: Annotated[int | None, Query(ge=1)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> RevisionPage:
        return await services.programs.revisions(program_id, caller, before=before, limit=limit)

    @app.post("/api/programs/{program_id}/validation", response_model=ProgramValidation)
    async def validate_program(
        program_id: str,
        command: ObservedProgramVersion,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramValidation:
        return await services.programs.validate(
            program_id, caller, expected_version=command.expected_version
        )

    @app.post(
        "/api/programs/{program_id}/revisions", response_model=ProgramRevision, status_code=201
    )
    async def publish_program(
        program_id: str,
        command: ObservedProgramVersion,
        caller: Annotated[Identity, Depends(authenticated)],
        services: Annotated[HttpServices, Depends(get_services)],
    ) -> ProgramRevision:
        return await services.programs.publish(
            program_id, caller, expected_version=command.expected_version
        )

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
        approved_by = None
        if request.workflow_access:
            principal = await human_principal(http_request, services)
            if not principal.owner.owns(caller):
                raise PermissionError("Workflow access owner differs from the authenticated owner")
            approved_by = principal.user
        return await services.executions.start(
            request,
            caller,
            credential_user_id=getattr(http_request.state, "authenticated_user", ""),
            approved_by=approved_by,
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
        if message.name.startswith(REVIEW_MESSAGE_PREFIX):
            raise HTTPException(403, "Internal review coordination messages are reserved")
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
