"""Source addresses participate in request identity independently of observed progress."""

import pytest
from pydantic import ValidationError

from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.identity import request_digest
from lumora.executions.domain.models import ExecutionPhase, ExecutionRecord
from lumora.programs.domain.models import ProgramRef
from lumora.services.identity.domain import Identity


@pytest.fixture
def child():
    owner = Identity.user("owner")
    return ExecutionRecord(
        execution_id="child",
        owner=owner,
        program=ProgramRef(program_id="root", revision=1),
        body_path=("map", "body"),
        content_digest="a" * 64,
        inputs={"item": 1},
        parent_execution_id="root-run",
        context=ExecutionContext(
            identity=owner,
            execution_id="child",
            engine_handle="native-child",
            root_execution_id="root-run",
            parent_execution_id="root-run",
            ancestor_execution_ids=("root-run",),
        ),
    )


def test_source_address_changes_request_identity_but_results_do_not(child):
    original = request_digest(child)
    assert request_digest(ExecutionRecord.model_validate_json(child.model_dump_json())) == original
    for field, value in (("body_path", ("other", "body")), ("content_digest", "b" * 64)):
        assert request_digest(child.model_copy(update={field: value})) != original
    completed = child.model_copy(
        update={"phase": ExecutionPhase.COMPLETED, "result": {"answer": 1}}
    )
    assert request_digest(completed) == original


def test_inline_source_requires_parent_and_digest(child):
    data = child.model_dump(mode="json")
    with pytest.raises(ValidationError, match="source digest"):
        ExecutionRecord.model_validate({**data, "content_digest": ""})
    data["parent_execution_id"] = None
    with pytest.raises(ValidationError, match="parent execution"):
        ExecutionRecord.model_validate(data)
