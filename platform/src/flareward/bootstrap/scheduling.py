"""Trusted tick admission observes the existing native run and owns transport clients."""

from typing import Any

from pydantic import JsonValue
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from runengine.core.refs import FunctionRef
from runengine.invocation.errors import InvocationContractError, InvocationInfrastructureError
from temporalio.client import Client

from flareward.async_work import await_owned
from flareward.bootstrap.settings.worker_settings import WorkerSettings
from flareward.bootstrap.workflow_access import WorkflowAccessComponents
from flareward.executions.access import ExecutionGrantAccess
from flareward.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from flareward.executions.adapters.run_engine.inbound.settings import load_receiver_settings
from flareward.executions.adapters.run_engine.outbound.errors import application_errors
from flareward.executions.adapters.run_engine.outbound.location import host_location
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.models import PreparedExecution
from flareward.services.access.credentials import WorkflowCredentialUnavailable
from flareward.services.scheduling.adapters.temporal.observation import TemporalExecutionObservation
from flareward.services.scheduling.adapters.temporal.programs import TemporalProgramSchedules
from flareward.services.scheduling.admission import ScheduledAdmission
from flareward.services.scheduling.programs import ProgramScheduleError, ScheduleRegistration
from flareward.services.sessions.adapters.mongo.session_store import MongoSessionStore

__runengine_contract__ = "flareward-schedule-admission-v2"


@application_errors
async def admit_scheduled_execution(
    registration: dict[str, JsonValue],
    context: dict[str, JsonValue],
    prepared: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    settings = await load_receiver_settings(WorkerSettings)
    prepared_execution = PreparedExecution.model_validate(prepared)
    if prepared_execution.location != host_location(settings.host):
        raise InvocationInfrastructureError(
            "Scheduled execution requires its original worker configuration", retryable=False
        )
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.mongo_uri.get_secret_value(), serverSelectionTimeoutMS=5000
    )
    try:
        database = client[settings.mongo_database]
        sessions = MongoSessionStore(database)
        await sessions.initialize()
        registration_value = ScheduleRegistration.model_validate(registration)
        records = MongoExecutionRepository(database)
        consents = workflow_access = calendar = None
        if registration_value.definition.request.workflow_access is not None:
            native = await Client.connect(settings.host.endpoint, namespace=settings.host.namespace)
            observation = TemporalExecutionObservation(settings.host, native)
            access = await WorkflowAccessComponents.create(
                settings, database, ExecutionGrantAccess(records, observation)
            )
            consents, workflow_access = access.consents, access.admission
            calendar = TemporalProgramSchedules(
                settings.host, FunctionRef.from_callable(admit_scheduled_execution), client=native
            )
        admitted = await ScheduledAdmission(
            records, sessions, consents=consents, workflow_access=workflow_access, calendar=calendar
        ).admit(
            registration_value.definition,
            ExecutionContext.model_validate(context),
            prepared_execution,
            registration=registration_value,
        )
        return admitted.model_dump(mode="json")
    except PyMongoError as error:
        raise InvocationInfrastructureError("Scheduled admission storage is unavailable") from error
    except WorkflowCredentialUnavailable, ProgramScheduleError:
        raise InvocationInfrastructureError("Scheduled workflow authority is unavailable") from None
    except PermissionError, ValueError:
        raise InvocationContractError("Scheduled workflow authorization was refused") from None
    finally:
        await await_owned(client.close())
