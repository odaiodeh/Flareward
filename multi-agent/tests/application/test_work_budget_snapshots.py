"""Admitted allowances are part of frozen request identity, distinct from input."""

import pytest
from mas.application.execution.models import PreparedExecution
from mas.core.identity import Identity
from mas.domain.execution.budgets import WorkLimits
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution.identity import request_digest
from mas.domain.execution.models import ExecutionRecord
from mas.domain.execution_preferences import ExecutionProfileCatalog
from mas.domain.programs.models import ProgramRef
from pydantic import ValidationError


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
