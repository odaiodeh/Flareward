"""Reusable data and service scenarios, independent of HTTP, engines, and databases."""

from typing import Protocol

from pydantic import JsonValue

from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.executions.domain.models import ExecutionRecord
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.executions.models import StartExecution
from lumora.executions.service import ExecutionService
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    ElementStep,
    GraphDefinition,
    ProgramDefinition,
    ProgramImplementation,
    ProgramRevision,
)
from lumora.programs.service import ProgramService
from lumora.resources.domain.bundles import ElementBundle, ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.identity.domain import Identity
from lumora.services.sessions.execution.program_sessions import ProgramSessionService
from lumora.services.sessions.records import SessionRecord
from support.elements import element_registry


class ProgramServices(Protocol):
    programs: ProgramService
    owner: Identity


class ExecutionServices(Protocol):
    executions: ExecutionService
    owner: Identity


def resource(
    rid: str,
    *,
    category: ResourceCategory = ResourceCategory.TOOL,
    config: dict[str, JsonValue] | None = None,
    type_key: str = "platform_dependency",
) -> ResourceDefinition:
    return ResourceDefinition(
        key=ResourceKey(category=category, rid=rid),
        type_key=type_key,
        config=config or {},
    )


def bundle() -> ElementBundle:
    return ElementBundleResolver(element_registry()).resolve(
        ResourceKey(category=ResourceCategory.NODE, rid="echo"),
        [
            resource(
                "echo",
                category=ResourceCategory.NODE,
                type_key="platform_echo",
                config={"dependency": "$ref:middle"},
            ),
            resource("middle", config={"dependency": "$ref:leaf", "value": "middle"}),
            resource("leaf"),
        ],
    )


async def publish(
    platform: ProgramServices,
    program_id: str,
    implementation: ProgramImplementation,
    *,
    execution_profile: str | None = None,
    input_schema: dict[str, JsonValue] | None = None,
    output_schema: dict[str, JsonValue] | None = None,
) -> ProgramRevision:
    interfaces = {}
    if input_schema is not None:
        interfaces["input_schema"] = input_schema
    if output_schema is not None:
        interfaces["output_schema"] = output_schema
    definition = ProgramDefinition(
        program_id=program_id,
        name=program_id,
        owner=platform.owner,
        implementation=implementation,
        execution_profile=execution_profile,
        **interfaces,
    )
    try:
        expected_version = (await platform.programs.draft(program_id, platform.owner)).version
    except KeyError:
        expected_version = 0
    draft = await platform.programs.save(
        definition, platform.owner, expected_version=expected_version
    )
    return await platform.programs.publish(
        program_id, platform.owner, expected_version=draft.version
    )


def echo_graph(profile: str = "thread") -> GraphDefinition:
    return GraphDefinition(
        steps=(
            ElementStep(
                uid="echo",
                element=ResourceKey(category=ResourceCategory.NODE, rid="echo"),
                execution=ExecutionSelection(profile=profile),
            ),
        ),
        resources=(
            resource(
                "echo",
                category=ResourceCategory.NODE,
                type_key="platform_echo",
                config={"dependency": "$ref:text"},
            ),
            resource("text", config={"value": "greeting"}),
        ),
        entry="echo",
        exit="echo",
        inputs={"user_prompt": PathBinding(path=("name",))},
        outputs={"answer": PathBinding(path=("output",))},
    )


async def run(
    platform: ExecutionServices,
    revision: ProgramRevision,
    inputs: JsonValue,
    execution_id: str | None = None,
) -> ExecutionRecord:
    record = await platform.executions.start(
        StartExecution(
            program=revision.reference,
            inputs=inputs,
            execution_id=execution_id,
        ),
        platform.owner,
    )
    return await platform.executions.result(record.execution_id, platform.owner)


async def finish_session(
    executions: ExecutionService, sessions: ProgramSessionService, record: SessionRecord
) -> SessionRecord:
    assert record.active_execution_id is not None
    await executions.result(record.active_execution_id, record.identity)
    return await sessions.refresh(record.run_id, record.identity)
