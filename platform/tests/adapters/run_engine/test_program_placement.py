"""Published placement constrains runtime selection without leaking engine types inward."""

from unittest.mock import create_autospec

import pytest
from runengine.coordination.ports import CoordinationOperations
from runengine.coordination.targets import EnvironmentTarget
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ExecutorConfig, ThreadRunnerConfig
from support.elements import element_registry
from support.scenarios import bundle, publish

from lumora.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from lumora.executions.adapters.run_engine.outbound.runtime import RunEngineProgramRuntime
from lumora.executions.adapters.run_engine.shared.models import (
    ElementSpecifications,
    ProgramPlacement,
)
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.preferences import ExecutionProfileCatalog, ExecutionSelection
from lumora.executions.placement import PlacementRefused
from lumora.programs.domain.models import ApplicationDefinition
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.identity.domain import Identity


@pytest.fixture
def runtime_case():
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.invoke.return_value = {"output": "done"}
    placement = ProgramPlacement(
        default_profile="thread",
        profiles={
            "thread": {"runner_type": "thread"},
            "process": {"runner_type": "process", "max_workers": 3},
        },
        environments=("shared",),
        child_imports={"child": {"local": "shared"}},
    )
    specifications = ElementSpecifications.from_registry(element_registry())
    specifications.catalog[ResourceCategory.LLM] = {
        "optional": FunctionRef(module="uninstalled_provider", qualname="UnusedSpec")
    }
    runtime = RunEngineProgramRuntime(
        operations, {}, specifications, ExecutionContext(identity=Identity.user("owner")), placement
    )
    return runtime, operations


@pytest.mark.parametrize(
    "selection", [ExecutionSelection(profile="process"), ExecutionSelection(environment="shared")]
)
async def test_invocation_selects_a_published_profile_or_environment(runtime_case, selection):
    runtime, operations = runtime_case
    result = await runtime.invoke_element(bundle(), {}, key="work", execution=selection)
    assert result == {"output": "done"}
    references = operations.invoke.call_args.args[0].kwargs["call"]["specifications"]
    assert {reference["qualname"] for reference in references} == {"EchoSpec", "DependencySpec"}
    target = operations.invoke.call_args.kwargs["target"]
    if selection.environment:
        assert isinstance(target, EnvironmentTarget) and target.name == "shared"
    else:
        assert isinstance(target, ExecutorConfig)
        assert target.model_dump() == {"runner_type": "process", "max_workers": 3}


@pytest.mark.parametrize(
    "selection", [ExecutionSelection(profile="unknown"), ExecutionSelection(environment="unknown")]
)
async def test_unknown_selection_is_refused_before_dispatch(runtime_case, selection):
    runtime, operations = runtime_case
    with pytest.raises(PlacementRefused):
        await runtime.invoke_element(bundle(), {}, key="work", execution=selection)
    operations.invoke.assert_not_awaited()


async def test_child_imports_cannot_escalate_beyond_published_bindings(runtime_case):
    runtime, operations = runtime_case
    with pytest.raises(ValueError, match="published bindings"):
        await runtime.start_child("child", {}, key="child", environment_imports={"local": "other"})
    operations.start_child.assert_not_awaited()


class DeniedProfiles:
    def __bool__(self) -> bool:
        return False

    def catalog(self, owner: Identity) -> ExecutionProfileCatalog:
        raise PermissionError("Owner refused")


async def test_injected_access_port_cannot_be_replaced_by_an_unrestricted_truthiness_fallback(
    application,
):
    revision = await publish(
        application, "denied", ApplicationDefinition(implementation="greeting", version="1")
    )
    compiler = ProgramCompiler(
        application.programs,
        application.elements,
        application.applications,
        {"thread": ThreadRunnerConfig()},
        "thread",
        profile_access=DeniedProfiles(),
    )
    with pytest.raises(PermissionError, match="Owner refused"):
        await compiler.compile(
            revision, application.owner, ExecutionContext(identity=application.owner)
        )
