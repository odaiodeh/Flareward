"""Published configuration is complete even when its authoring started unfinished."""

import pytest
from support.application import Application, make_application
from support.draft_configuration import (
    APPLICATION_PROGRAMS,
    ELEMENT_SPECIFICATIONS,
    complete_configuration,
    definition,
    incomplete_configuration,
    unfinished_resource_graph,
)
from support.scenarios import publish, run
from support.secrets import MemorySecretStore

from flareward.programs.domain.models import ApplicationDefinition, ProgramBody
from flareward.programs.service import ProgramContractError


@pytest.fixture
def application() -> Application:
    application = make_application(MemorySecretStore())
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    return application


async def test_incomplete_configuration_completes_and_runs_owned_and_published(platform):
    root = definition(platform.owner, incomplete_configuration())
    saved = await platform.programs.save(root, platform.owner)
    with pytest.raises(ProgramContractError):
        await platform.programs.publish(
            "configured", platform.owner, expected_version=saved.version
        )
    config = complete_configuration(saved.definition.implementation.config)
    complete = await platform.programs.save(
        definition(platform.owner, config), platform.owner, expected_version=saved.version
    )
    revision = await platform.programs.publish(
        "configured", platform.owner, expected_version=complete.version
    )
    direct = await run(platform, revision, {})
    assert direct.result == {"title": "Completed configuration", "endpoint": "connection"}
    for target in (
        revision.reference,
        ProgramBody(implementation=revision.definition.implementation),
    ):
        caller = await publish(
            platform,
            "caller",
            ApplicationDefinition(
                implementation="composed", version="1", children={"greet": target}
            ),
        )
        nested = await run(platform, caller, {})
        assert nested.result == direct.result
    unfinished = await platform.programs.save(
        saved.definition, platform.owner, expected_version=complete.version
    )
    assert not (
        await platform.programs.validate(
            "configured", platform.owner, expected_version=unfinished.version
        )
    ).valid
    assert await platform.programs.revision(revision.reference, platform.owner) == revision
    assert (await run(platform, revision, {})).result == direct.result


async def test_incomplete_graph_resource_is_protected_and_requires_completion_before_publication(
    platform,
):
    root = definition(platform.owner, {}).model_copy(
        update={"implementation": unfinished_resource_graph()}
    )
    saved = await platform.programs.save(root, platform.owner)
    assert "bundle-private" not in saved.model_dump_json()
    with pytest.raises(ProgramContractError):
        await platform.programs.publish(
            "configured", platform.owner, expected_version=saved.version
        )
    graph = saved.definition.implementation
    private = graph.resources[1].model_copy(
        update={"config": {**graph.resources[1].config, "endpoint": "constructed"}}
    )
    completed = await platform.programs.save(
        saved.definition.model_copy(
            update={
                "implementation": graph.model_copy(
                    update={"resources": (graph.resources[0], private)}
                )
            }
        ),
        platform.owner,
        expected_version=saved.version,
    )
    revision = await platform.programs.publish(
        "configured", platform.owner, expected_version=completed.version
    )
    assert revision.definition == completed.definition
