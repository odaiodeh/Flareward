"""Native child history accepts started runs, rejects malformed identity, and detaches inputs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from runengine.adapters.coordination.temporal.host import TemporalRunHandle
from runengine.adapters.coordination.temporal.models import RunParameters
from runengine.adapters.coordination.temporal.protocol import WORKFLOW_NAME
from runengine.coordination.enums import RunFailureCode
from runengine.coordination.errors import RunContractError
from runengine.coordination.models import RunRequest
from runengine.programs.graph.entrypoint import run_graph
from temporalio.api.common.v1 import WorkflowType
from temporalio.api.enums.v1 import EventType
from temporalio.api.history.v1 import (
    ChildWorkflowExecutionStartedEventAttributes,
    HistoryEvent,
    StartChildWorkflowExecutionInitiatedEventAttributes,
)
from temporalio.converter import DataConverter


@pytest.mark.parametrize("mismatch", [False, True])
async def test_history_reports_only_accepted_children_and_validates_native_identity(mismatch):
    request = RunRequest.create(
        run_graph,
        run_id="wrong" if mismatch else "child",
        parent_run_id="parent",
        input={"value": 1},
    )
    parameters = RunParameters(request=request)
    payload = await DataConverter.default.encode_wrapper([parameters.model_dump(mode="json")])
    accepted = HistoryEvent(
        event_id=1,
        event_type=EventType.EVENT_TYPE_START_CHILD_WORKFLOW_EXECUTION_INITIATED,
        start_child_workflow_execution_initiated_event_attributes=(
            StartChildWorkflowExecutionInitiatedEventAttributes(
                workflow_id="child",
                workflow_type=WorkflowType(name=WORKFLOW_NAME),
                input=payload,
            )
        ),
    )
    started = HistoryEvent(
        event_id=2,
        event_type=EventType.EVENT_TYPE_CHILD_WORKFLOW_EXECUTION_STARTED,
        child_workflow_execution_started_event_attributes=(
            ChildWorkflowExecutionStartedEventAttributes(initiated_event_id=1)
        ),
    )
    rejected = HistoryEvent(
        event_id=3,
        event_type=EventType.EVENT_TYPE_START_CHILD_WORKFLOW_EXECUTION_INITIATED,
        start_child_workflow_execution_initiated_event_attributes=(
            StartChildWorkflowExecutionInitiatedEventAttributes(workflow_id="never-started")
        ),
    )
    native = AsyncMock()
    native.describe.return_value = SimpleNamespace(
        namespace="default", id="parent", run_id="first", data_converter=DataConverter.default
    )
    native.fetch_history.return_value = SimpleNamespace(events=[accepted, started, rejected])
    handle = TemporalRunHandle(native, "parent")
    if mismatch:
        with pytest.raises(RunContractError) as error:
            await handle.children()
        assert error.value.code == RunFailureCode.INVALID_REQUEST
    else:
        children = await handle.children()
        assert len(children) == 1 and children[0] == request
        children[0].input["value"] = "reader mutation"
        assert (await handle.children())[0].input == {"value": 1}
