"""Admitted allowances are part of frozen request identity, distinct from input."""

import pytest
from pydantic import ValidationError

from flareward.executions.domain.budgets import WorkLimits
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.identity import request_digest
from flareward.executions.domain.models import ExecutionRecord
from flareward.executions.domain.preferences import ExecutionProfileCatalog
from flareward.executions.models import PreparedExecution
from flareward.programs.domain.models import ProgramRef
from flareward.services.identity.domain import Identity


def test_prepared_budget_metadata_cannot_change_under_its_existing_digest():
    prepared = PreparedExecution(
        format="test/1", payload_json='{"input":{}}', work_limits=WorkLimits()
    )
    with pytest.raises(ValidationError, match="digest mismatch"):
        PreparedExecution.model_validate(
            {**prepared.model_dump(), "work_limits": {"max_dispatches": 1}}
        )


def test_admitted_work_limits_are_execution_request_identity():
    owner = Identity.user("owner")
    record = ExecutionRecord(
        execution_id="root",
        owner=owner,
        program=ProgramRef(program_id="program", revision=1),
        inputs={},
        context=ExecutionContext(identity=owner),
        work_limits=WorkLimits(),
    )
    assert request_digest(record) != request_digest(
        record.model_copy(update={"work_limits": WorkLimits(max_dispatches=1)})
    )


def test_admitted_profiles_cannot_change_under_frozen_prepared_or_request_identity():
    profiles = ExecutionProfileCatalog(profiles=("allowed",), default_profile="allowed")
    prepared = PreparedExecution(format="test/1", payload_json="{}", admitted_profiles=profiles)
    with pytest.raises(ValidationError, match="digest mismatch"):
        PreparedExecution.model_validate({**prepared.model_dump(), "admitted_profiles": None})
    owner = Identity.user("owner")
    record = ExecutionRecord(
        execution_id="root",
        owner=owner,
        program=ProgramRef(program_id="program", revision=1),
        inputs={},
        context=ExecutionContext(identity=owner),
        admitted_profiles=profiles,
    )
    assert request_digest(record) != request_digest(
        record.model_copy(update={"admitted_profiles": None})
    )
