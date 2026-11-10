"""Portable invocations distinguish operation identity from graph adapter context."""

import pytest
from pydantic import ValidationError
from support.operations import operation_bundle
from support.scenarios import bundle

from lumora.executions.adapters.run_engine.shared.models import ElementCall
from lumora.executions.domain.context import ExecutionContext
from lumora.programs.graph.models.step_context import StepContext


def test_typed_operation_call_needs_no_graph_context(application):
    call = ElementCall(
        bundle=operation_bundle(application.elements),
        specifications=(),
        context=ExecutionContext(identity=application.owner),
        key="operation-key",
    )
    assert call.step is None
    assert ElementCall.model_validate_json(call.model_dump_json()) == call
    with pytest.raises(ValueError, match="no graph step context"):
        _ = call.graph_step
    with pytest.raises(ValidationError, match="cannot carry graph step context"):
        ElementCall.model_validate({**call.model_dump(), "step": StepContext(uid=call.key)})


@pytest.mark.parametrize("step", (None, StepContext(uid="different")))
def test_graph_call_requires_matching_authored_context(application, step):
    with pytest.raises(ValidationError, match="matching their invocation key"):
        ElementCall(
            bundle=bundle(),
            specifications=(),
            context=ExecutionContext(identity=application.owner),
            key="graph-key",
            step=step,
        )


def test_graph_call_keeps_its_explicit_context(application):
    step = StepContext(uid="graph-key", branches={"approved": "next"})
    call = ElementCall(
        bundle=bundle(),
        specifications=(),
        context=ExecutionContext(identity=application.owner),
        key=step.uid,
        step=step,
    )
    assert call.graph_step == step
