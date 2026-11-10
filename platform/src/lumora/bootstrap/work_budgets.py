"""Receiver-private durable work admission, invoked through native journaled operations."""

from typing import Any

from pydantic import JsonValue, ValidationError
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from runengine.core.enums import FailureOrigin
from runengine.core.failure import FailureDescriptor
from runengine.invocation.errors import InvocationContractError, InvocationInfrastructureError

from lumora.bootstrap.settings.receiver_settings import ReceiverSettings
from lumora.executions.adapters.mongo.work_budgets import MongoWorkBudgets
from lumora.executions.adapters.run_engine.inbound.settings import load_receiver_settings
from lumora.executions.budgets import WorkAdmission
from lumora.executions.domain.budgets import WorkBudgetConflict, WorkLimitExceeded

__runengine_contract__ = "lumora-work-admission-v1"


async def admit_work(*, request: dict[str, JsonValue]) -> None:
    settings = await load_receiver_settings(ReceiverSettings)
    try:
        admission = WorkAdmission.model_validate(request)
        client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
            settings.mongo_uri.get_secret_value(),
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )
        async with client:
            repository = MongoWorkBudgets(client[settings.mongo_database])
            if admission.reservation is None:
                await repository.initialize(admission.budget)
            else:
                await repository.reserve(admission.budget, admission.reservation)
    except WorkLimitExceeded as error:
        raise InvocationContractError(
            str(error),
            failure=FailureDescriptor(
                origin=FailureOrigin.CONTRACT,
                code="WORK_LIMIT_EXCEEDED",
                error_type="WorkLimitExceeded",
                message=str(error),
                details={"dimension": error.dimension},
            ),
        ) from None
    except WorkBudgetConflict as error:
        raise InvocationContractError(str(error)) from None
    except ValidationError:
        raise InvocationContractError("Execution-tree admission request is invalid") from None
    except PyMongoError:
        raise InvocationInfrastructureError(
            "Execution-tree admission storage is unavailable", retryable=True
        ) from None
