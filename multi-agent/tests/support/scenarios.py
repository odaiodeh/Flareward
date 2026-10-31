"""Reusable data and service scenarios, independent of HTTP, engines, and databases."""

from typing import Protocol

from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.element_bundles import ElementBundle, ResourceDefinition, ResourceKey
from mas.execution.models import ExecutionRecord, StartExecution
from mas.execution.service import ExecutionService
from mas.programs.models import (
    ElementStep,
    ExecutionSelection,
    GraphDefinition,
    PathBinding,
    ProgramDefinition,
    ProgramImplementation,
    ProgramRevision,
)
from mas.programs.service import ProgramService
from mas.session.domain.session_record import SessionRecord
from mas.session.execution.program_sessions import ProgramSessionService
from pydantic import JsonValue

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
) -> ProgramRevision:
    definition = ProgramDefinition(
        program_id=program_id,
        name=program_id,
        owner=platform.owner,
        implementation=implementation,
    )
    await platform.programs.save(definition, platform.owner)
    return await platform.programs.publish(program_id, platform.owner)


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
