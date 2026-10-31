"""Credential references survive replay while plaintext remains inside invocation construction."""

import asyncio
import hashlib

import pytest
from mas.execution.models import ExecutionPhase, StartExecution
from support.elements import element_registry
from support.secrets import secret_definition
from support.temporal import replay

from bootstrap.platform import compose_platform
from bootstrap.worker import compose_worker


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("fail", [False, True])
async def test_temporal_history_excludes_secret_values_on_success_and_failure(
    durable, secret_settings, profile, fail
):
    token = "private-temporal-credential"
    settings = secret_settings.model_copy(update={"host": durable.settings.host})
    async with compose_worker(durable.settings):
        async with compose_platform(settings, elements=element_registry()) as services:
            definition = secret_definition(profile, token, fail_on_run=fail)
            protected = await services.programs.save(definition, definition.owner)
            revision = await services.programs.publish(definition.program_id, definition.owner)
            assert token not in protected.model_dump_json() + revision.model_dump_json()
            record = await services.executions.start(
                StartExecution(program=revision.reference), definition.owner
            )
            async with asyncio.timeout(20):
                result = await services.executions.result(record.execution_id, definition.owner)
            if fail:
                assert result.phase == ExecutionPhase.FAILED, result
                assert "ValueError" in result.failure.message
            else:
                assert result.phase == ExecutionPhase.COMPLETED, result.failure
                assert result.result == {"digest": hashlib.sha256(token.encode()).hexdigest()}
            history = await durable.client.get_workflow_handle(record.engine_handle).fetch_history()
            assert token not in history.to_json() and token not in result.model_dump_json()
            await replay(durable.client, durable.settings, record.engine_handle)
