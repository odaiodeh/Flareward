"""An optional repository capability composes through the ordinary graph/code runtime."""

import json

import pytest
from support.scenarios import publish, run

from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.domain.models import ExecutionPhase
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    OperationStep,
    PathBinding,
    ProgramCallStep,
)
from flareward.resources.domain.bundles import ResourceDefinition, ResourceKey
from flareward.resources.domain.categories import ResourceCategory
from plugins.git.elements.specification import ELEMENT_SPECIFICATIONS


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_graph_resolves_candidate_and_code_child_materializes_it(
    platform, application, local_repository, tmp_path, monkeypatch, profile
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    root = tmp_path / "compute"
    monkeypatch.setenv("FLAREWARD_WORKSPACE_ROOT", str(root))
    monkeypatch.setenv(
        "FLAREWARD_GIT_REPOSITORIES",
        json.dumps(
            {
                "source": {
                    "location": str(local_repository.path),
                    "owners": [platform.owner.model_dump(mode="json")],
                }
            }
        ),
    )
    provider = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.PROVIDER, rid="source"),
        type_key="git_repository",
        config={"repository": "source"},
    )
    resolver = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="resolve"),
        type_key="resolve_git_revision",
        config={"source": "$ref:source"},
    )
    checkout = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="checkout"),
        type_key="checkout_git_revision",
        config={"source": "$ref:source"},
    )
    bundle = ElementBundleResolver(application.elements).resolve(checkout.key, (checkout, provider))
    child = await publish(
        platform,
        "materialize-source",
        ApplicationDefinition(
            implementation="placed_operation",
            version="1",
            config={"bundle": bundle.model_dump(mode="json"), "execution": {"profile": profile}},
        ),
    )
    parent = await publish(
        platform,
        "source-workflow",
        GraphDefinition(
            resources=(resolver, provider),
            steps=(
                OperationStep(
                    uid="resolve",
                    element=resolver.key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={"reference": PathBinding(path=("input", "reference"))},
                    outputs={"values": PathBinding(path=())},
                ),
                ProgramCallStep(
                    uid="checkout",
                    program=child.reference,
                    inputs={"revision": PathBinding(path=("values",))},
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            edges={"resolve": ("checkout",)},
            entry="resolve",
            exit="checkout",
            outputs={"source": PathBinding(path=("values",))},
        ),
    )
    commit = await local_repository.git("rev-parse", "HEAD")
    record = await run(platform, parent, {"reference": "refs/heads/main"})
    assert record.phase == ExecutionPhase.COMPLETED, record.failure
    result = record.result["source"]
    assert result["revision"] == {"repository": "source", "commit": commit}
    assert (root / result["workspace"] / "answer.txt").read_text() == "first candidate"
    children = await platform.executions.children(record.execution_id, platform.owner)
    assert len(children) == 1 and children[0].program == child.reference
    portable = json.dumps(record.result) + parent.model_dump_json() + child.model_dump_json()
    assert str(local_repository.path) not in portable
    assert "artifact_id" not in portable
