"""Application-only trusted-check scenario, shared by port and native tests."""

import json
from typing import Any

from pydantic import JsonValue

from flareward.elements.factory import BaseFactory
from flareward.elements.operation import BaseOperation, OperationContext
from flareward.elements.specification import BaseElementSpec
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.models import Model
from flareward.programs.domain.models import (
    GraphDefinition,
    OperationStep,
    PathBinding,
    ProgramDefinition,
)
from flareward.resources.domain.bundles import ResourceDefinition, ResourceKey
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.identity.domain import Identity
from flareward.services.verification.domain.models import CheckVerdict
from flareward.services.verification.program_checks import CheckProgramInput, CheckProgramResult


class ValueCheckConfig(Model):
    expected: JsonValue


class ValueCheck(BaseOperation[CheckProgramInput, CheckProgramResult]):
    def __init__(self, expected: JsonValue) -> None:
        self._expected = json.dumps(expected, sort_keys=True, separators=(",", ":"))

    async def execute(
        self, request: CheckProgramInput, context: OperationContext
    ) -> CheckProgramResult:
        actual = json.dumps(
            request.subject.identity["value"], sort_keys=True, separators=(",", ":")
        )
        return CheckProgramResult(
            subject_fingerprint=request.subject.fingerprint,
            verdict=CheckVerdict.PASSED if actual == self._expected else CheckVerdict.FAILED,
            details={"execution_id": context.execution.execution_id, "key": context.key},
        )


class ValueCheckFactory(BaseFactory):
    def accepts(self, cfg: ValueCheckConfig, element_type: str) -> bool:
        return element_type == "fixture_value_check"

    def create(self, cfg: ValueCheckConfig, **dependencies: Any) -> ValueCheck:
        return ValueCheck(cfg.expected)


class ValueCheckSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "fixture_value_check"
    name = "Controlled value verifier"
    description = "Checks an exact JSON value; does not execute candidate code"
    config_schema = ValueCheckConfig
    factory_cls = ValueCheckFactory
    input_schema = CheckProgramInput
    result_schema = CheckProgramResult


ELEMENT_SPECIFICATIONS = (ValueCheckSpec,)


def verifier_definition(owner: Identity, profile: str = "thread") -> ProgramDefinition:
    operation = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="check"),
        type_key=ValueCheckSpec.type_key,
        config={"expected": 42},
    )
    inputs = ("intent_id", "plan_id", "check", "subject")
    return ProgramDefinition(
        program_id="trusted-verifier",
        name="Trusted fixture verifier",
        owner=owner,
        implementation=GraphDefinition(
            resources=(operation,),
            steps=(
                OperationStep(
                    uid="check",
                    element=operation.key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={name: PathBinding(path=("values", name)) for name in inputs},
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            entry="check",
            exit="check",
            inputs={"values": PathBinding(path=())},
            outputs={
                name: PathBinding(path=("values", name))
                for name in ("subject_fingerprint", "verdict", "details")
            },
        ),
        input_schema=CheckProgramInput.model_json_schema(),
        output_schema=CheckProgramResult.model_json_schema(),
    )
