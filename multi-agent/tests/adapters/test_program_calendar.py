"""Calendar transport failures and owner checks do not expose action payloads."""

from unittest.mock import AsyncMock, create_autospec

import pytest
from mas.core.identity import Identity
from mas.scheduling.programs import ProgramScheduleError
from outbound.temporal.program_schedules import TemporalProgramSchedules
from runengine.adapters.coordination.config import TemporalHostConfig
from runengine.core.refs import FunctionRef
from temporalio.client import Client, ScheduleDescription, ScheduleHandle

from bootstrap.scheduling import admit_scheduled_execution


async def test_calendar_connection_failure_is_safe_infrastructure_failure(monkeypatch):
    connect = AsyncMock(side_effect=RuntimeError("private connection diagnostics"))
    monkeypatch.setattr(Client, "connect", connect)
    backend = TemporalProgramSchedules(
        TemporalHostConfig(), FunctionRef.from_callable(admit_scheduled_execution)
    )
    with pytest.raises(ProgramScheduleError, match="Calendar service is unavailable") as caught:
        await backend.get("schedule", Identity.user("alice"))
    assert "private" not in str(caught.value)
    connect.assert_awaited_once()


async def test_calendar_authorizes_memo_owner_before_decoding_private_action():
    client = create_autospec(Client, instance=True)
    client.namespace = "default"
    handle = create_autospec(ScheduleHandle, instance=True)
    description = create_autospec(ScheduleDescription, instance=True)
    description.memo_value.return_value = Identity.user("other").model_dump(mode="json")
    handle.describe.return_value = description
    client.get_schedule_handle.return_value = handle
    backend = TemporalProgramSchedules(
        TemporalHostConfig(), FunctionRef.from_callable(admit_scheduled_execution), client=client
    )
    with pytest.raises(PermissionError):
        await backend.get("schedule", Identity.user("alice"))
    client.data_converter.decode.assert_not_called()
