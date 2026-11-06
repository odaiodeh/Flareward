"""Trusted tick admission observes the existing native run and owns transport clients."""

from typing import Any

from inbound.run_engine.settings import load_receiver_settings
from mas.application.access.credentials import WorkflowCredentialUnavailable
from mas.application.execution.access import ExecutionGrantAccess
from mas.application.execution.models import PreparedExecution
from mas.core.async_work import await_owned
from mas.domain.execution.context import ExecutionContext
from mas.scheduling.admission import ScheduledAdmission
from mas.scheduling.programs import ProgramScheduleError, ScheduleRegistration
from outbound.mongo.execution_repository import MongoExecutionRepository
from outbound.mongo.session_store import MongoSessionStore
from outbound.run_engine.errors import application_errors
from outbound.run_engine.location import host_location
from outbound.temporal.execution_observation import TemporalExecutionObservation
from outbound.temporal.program_schedules import TemporalProgramSchedules
from pydantic import JsonValue
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from runengine.core.refs import FunctionRef
from runengine.invocation.errors import InvocationContractError, InvocationInfrastructureError
from temporalio.client import Client

from bootstrap.workflow_access import WorkflowAccessComponents
from config.worker_settings import WorkerSettings

__runengine_contract__ = "unifai-schedule-admission-v2"


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
