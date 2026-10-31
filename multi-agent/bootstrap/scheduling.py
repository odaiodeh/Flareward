"""Receiver-local business admission; no execution host or HTTP server is created."""

from typing import Any

from inbound.run_engine.settings import load_receiver_settings
from mas.core.async_work import await_owned
from mas.core.execution_context import ExecutionContext
from mas.execution.models import PreparedExecution
from mas.scheduling.admission import ScheduledAdmission
from mas.scheduling.programs import ProgramSchedule
from outbound.mongo.execution_repository import MongoExecutionRepository
from outbound.mongo.session_store import MongoSessionStore
from outbound.run_engine.location import host_location
from pydantic import JsonValue
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from runengine.invocation.errors import InvocationInfrastructureError

from config.worker_settings import WorkerSettings

__runengine_contract__ = "unifai-schedule-admission-v1"


async def admit_scheduled_execution(
    definition: dict[str, JsonValue], context: dict[str, JsonValue], prepared: dict[str, JsonValue]
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
        admitted = await ScheduledAdmission(MongoExecutionRepository(database), sessions).admit(
            ProgramSchedule.model_validate(definition),
            ExecutionContext.model_validate(context),
            prepared_execution,
        )
        return admitted.model_dump(mode="json")
    except PyMongoError as error:
        raise InvocationInfrastructureError("Scheduled admission storage is unavailable") from error
    finally:
        await await_owned(client.close())
