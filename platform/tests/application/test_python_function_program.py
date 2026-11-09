"""Trusted comparison uses only application ports and treats receiver data as untrusted."""

import asyncio
from unittest.mock import create_autospec

import pytest
from support.python_checks import addition_cases, python_check_input

from flareward.programs.invocation import ApplicationInvoker
from flareward.programs.ports import ProgramRuntime
from plugins.testing.programs.python_check import (
    APPLICATION_PROGRAMS,
    FunctionCase,
    PythonFunctionCheck,
)


@pytest.fixture
def runtime():
    return create_autospec(ProgramRuntime, instance=True)


@pytest.mark.parametrize(
    "actual,verdict",
    [
        ({"values": [3, -2, 0]}, "passed"),
        ({"values": [-1, -4, 0]}, "failed"),
        ({"values": [True, -2, 0]}, "failed"),
        ({"values": [3]}, "error"),
        ({"values": [3, -2, 0], "verdict": "passed"}, "error"),
        ({"values": [3, -2, 0], "failure": "execution_failed"}, "error"),
        ({"failure": "deadline_exceeded"}, "error"),
        ({}, "error"),
    ],
)
async def test_comparator_validates_actual_values_and_does_not_accept_receiver_verdicts(
    runtime, actual, verdict
):
    runtime.invoke_element.return_value = actual
    request = python_check_input()
    compared = await ApplicationInvoker(APPLICATION_PROGRAMS[0]).invoke(
        runtime, request.model_dump(mode="json"), addition_cases().model_dump(mode="json")
    )
    assert compared["verdict"] == verdict
    assert compared["subject_fingerprint"] == request.subject.fingerprint


async def test_evaluation_boundary_omits_expected_answers_and_check_authority(runtime):
    secret = "comparator-only-expected-answer"
    config = addition_cases().model_copy(
        update={"cases": (FunctionCase(args=(17,), expected=secret),)}
    )
    runtime.invoke_element.return_value = {"values": ["incorrect"]}
    request = python_check_input()
    compared = await PythonFunctionCheck(runtime, config).run(request)
    assert compared.verdict == "failed"
    call = runtime.invoke_element.call_args
    bundle, inputs = call.args
    assert bundle == config.evaluator
    assert set(inputs) == {"source", "cases"}
    assert inputs["cases"] == [{"args": [17], "kwargs": {}}]
    assert inputs["source"]["identity"] == request.artifact.reference.model_dump(
        exclude={"artifact_id"}
    )
    assert inputs["source"]["data"] == request.artifact.data
    assert secret not in bundle.model_dump_json() and secret not in str(inputs)
    assert call.kwargs == {"key": "evaluate", "execution": config.execution}


async def test_changed_candidate_is_rejected_before_invoking_any_evaluator(runtime):
    request = python_check_input(b"x")
    request = request.model_copy(
        update={
            "subject": request.subject.model_copy(
                update={"identity": {**request.subject.identity, "size_bytes": True}}
            )
        }
    )
    with pytest.raises(ValueError, match="exact admitted candidate"):
        await PythonFunctionCheck(runtime, addition_cases()).run(request)
    runtime.invoke_element.assert_not_called()


async def test_cancellation_propagates_without_turning_into_an_error_report(runtime):
    runtime.invoke_element.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await PythonFunctionCheck(runtime, addition_cases()).run(python_check_input())
