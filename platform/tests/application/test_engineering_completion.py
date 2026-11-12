"""One ADLC coordinator selects only published, typed completion policies."""

from dataclasses import replace
from unittest.mock import AsyncMock, create_autospec

import pytest
from pydantic import ValidationError
from support.check_runs import MemoryCheckRunRepository, check_policy, source_policy
from support.completion_contracts import CANDIDATES, FileCandidate, GitCandidate
from support.engineering_programs import COORDINATORS as PRODUCERS
from support.engineering_programs import engineering_configuration
from support.engineering_runtime import ServiceRuntime
from support.review_programs import review_body
from support.scenarios import publish
from support.verification import MemoryVerificationRepository

from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramBody
from lumora.programs.ports import ChildExecution
from lumora.programs.service import ProgramContractError
from lumora.services.reviews.domain.models import ReviewDecision
from lumora.services.verification.check_service import CheckRunService, RegisteredCheckRunner
from lumora.services.verification.domain.models import CheckVerdict
from lumora.services.verification.service import VerificationService
from plugins.adlc.programs.program import (
    COORDINATORS,
    EngineeringConfig,
    EngineeringInput,
    EngineeringResult,
    EngineeringWork,
    engineering,
)
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from plugins.human_review.programs.human_review import COORDINATORS as REVIEW_PROGRAMS
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS as CHECKS


@pytest.fixture
def completion_config(application):
    for spec in (*REVIEWS, *CHECKS):
        application.elements.register_spec_class(spec)
    config = engineering_configuration(application.elements)
    template = config.completions[0].model_dump()
    return EngineeringConfig.model_validate(
        {
            **config.model_dump(),
            "default_completion": "files",
            "completions": [
                {
                    **template,
                    "name": name,
                    "candidate_schema": candidate.model_json_schema(),
                    "implementation": name,
                    "repair": name + "-repair",
                    "verification_policy": name + "@1",
                    "runners": [name + "-ci@1"],
                }
                for name, candidate in (("files", FileCandidate), ("git", GitCandidate))
            ],
        }
    )


def completion_runtime(candidate_values=None):
    runtime = ServiceRuntime([CheckVerdict.PASSED], [ReviewDecision.APPROVE])
    values = candidate_values or {
        name: candidate.model_dump(mode="json") for name, candidate in CANDIDATES.items()
    }
    policies = {
        name + "@1": source_policy(runtime.owner).model_copy(
            update={"subject_kind": value["subject"]["kind"]}
        )
        for name, value in values.items()
    }
    runtime.actor = replace(
        runtime.actor,
        scope=runtime.actor.scope.model_copy(update={"policies": frozenset(policies)}),
    )
    runtime.verification = VerificationService(
        MemoryVerificationRepository(), policies, clock=runtime.clock
    )
    runtime.checks = CheckRunService(
        MemoryCheckRunRepository(),
        runtime.verification,
        {
            name + "-ci@1": RegisteredCheckRunner(
                check_policy(runtime.owner).model_copy(
                    update={
                        "policies": frozenset({name + "@1"}),
                        "subject_kind": value["subject"]["kind"],
                    }
                ),
                runtime.runner,
            )
            for name, value in values.items()
        },
        clock=runtime.clock,
    )

    async def start_child(name, inputs, *, key, environment_imports=None):
        if name == "reviewer":
            return runtime.review_children.start(inputs, key)
        runtime.work.append((name, inputs))
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = "candidate"
        child.result.return_value = values[name]
        return child

    runtime.start_child = start_child
    return runtime


@pytest.mark.parametrize(
    "selection,expected", [(None, "files"), ("files", "files"), ("git", "git")]
)
async def test_same_configuration_selects_declared_deliverable_and_acceptance(
    completion_config, selection, expected
):
    frozen = completion_config.model_dump_json()
    runtime = completion_runtime()
    result = EngineeringResult.model_validate(
        await engineering(
            runtime, {"task": "implement", "completion": selection}, completion_config
        )
    )
    assert result.outcome == "verified" and result.completion == expected
    assert runtime.work[0][0] == expected
    assert (
        result.candidate.model_dump(mode="json")
        == CANDIDATES[expected].model_dump(mode="json")["subject"]
    )
    assert result.verification.state.plan.policy == expected + "@1"
    assert result.review.review.specification.subject["completion"] == expected
    assert completion_config.model_dump_json() == frozen


async def test_undeclared_selection_dispatches_no_work(completion_config):
    runtime = completion_runtime()
    with pytest.raises(ValueError, match="not declared"):
        await engineering(
            runtime, {"task": "implement", "completion": "private-policy"}, completion_config
        )
    assert not runtime.work and runtime.runner.submissions == 0


@pytest.mark.parametrize("invalid", ["kind", "mutable-commit", "missing-field"])
async def test_invalid_worker_result_cannot_request_checks_or_review(completion_config, invalid):
    value = CANDIDATES["git"].model_dump(mode="json")
    if invalid == "kind":
        value["subject"]["kind"] = "private-kind"
    elif invalid == "mutable-commit":
        value["subject"]["identity"]["commit"] = "refs/heads/private-branch"
    else:
        del value["subject"]["identity"]["repository"]
    runtime = completion_runtime({"git": value})
    effects = AsyncMock(wraps=runtime.invoke_element)
    runtime.invoke_element = effects
    with pytest.raises(ValueError, match="selected candidate contract") as error:
        await engineering(runtime, {"task": "implement", "completion": "git"}, completion_config)
    assert "private" not in str(error.value)
    assert runtime.runner.submissions == 0
    effects.assert_not_awaited()


@pytest.mark.parametrize(
    "invalid",
    [
        "duplicate-name",
        "missing-default",
        "remote-schema",
        "bad-schema",
        "shared-alias",
        "reviewer-alias",
    ],
)
def test_invalid_completion_declarations_fail_closed(completion_config, invalid):
    config = completion_config.model_dump(mode="json")
    if invalid == "duplicate-name":
        config["completions"][1]["name"] = "files"
    elif invalid == "missing-default":
        config["default_completion"] = "unknown"
    elif invalid == "remote-schema":
        config["completions"][0]["candidate_schema"] = {
            "$ref": "https://example.invalid/private-schema"
        }
    elif invalid == "bad-schema":
        config["completions"][0]["candidate_schema"] = {"type": "not-a-type"}
    elif invalid == "reviewer-alias":
        config["completions"][0]["review"]["program"] = "files"
    else:
        config["completions"][1]["implementation"] = "files"
    with pytest.raises(ValidationError) as error:
        EngineeringConfig.model_validate(config)
    assert "private-schema" not in str(error.value)


@pytest.mark.parametrize("mismatch", [False, True])
async def test_publication_checks_configured_candidate_contracts(
    application, completion_config, mismatch
):
    for registration in (*COORDINATORS, *PRODUCERS, *REVIEW_PROGRAMS):
        application.applications.register(registration)
    children = {}
    for choice in completion_config.completions:
        schema = FileCandidate.model_json_schema() if mismatch else choice.candidate_schema
        body = ProgramBody(
            implementation=CustomCoordinatorDefinition(
                implementation="engineering_candidate", version="1"
            ),
            input_schema=EngineeringWork.model_json_schema(),
            output_schema=schema,
        )
        children[choice.implementation] = body
        children[choice.repair] = body
    definition = CustomCoordinatorDefinition(
        implementation="engineering",
        version="4",
        config=completion_config.model_dump(mode="json"),
        children={**children, "reviewer": review_body(application.elements)},
    )
    if mismatch:
        with pytest.raises(ProgramContractError, match="cannot satisfy"):
            await publish(
                application,
                "completion",
                definition,
                input_schema=EngineeringInput.model_json_schema(),
                output_schema=EngineeringResult.model_json_schema(),
            )
    else:
        await publish(
            application,
            "completion",
            definition,
            input_schema=EngineeringInput.model_json_schema(),
            output_schema=EngineeringResult.model_json_schema(),
        )
