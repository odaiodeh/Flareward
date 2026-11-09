"""Production coding and transfer operations hand work between graph and code programs."""

import os
import shutil
from uuid import uuid4

import pytest
from runengine.adapters.coordination.config import LocalHostConfig
from support.scenarios import publish, run
from support.server import api_process

from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.domain.models import ExecutionPhase
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    LiteralBinding,
    OperationStep,
    PathBinding,
)
from flareward.resources.domain.bundles import ResourceDefinition, ResourceKey
from flareward.resources.domain.categories import ResourceCategory
from plugins.adlc.programs.coding import APPLICATION_PROGRAMS, CodingFileCandidateConfig
from plugins.artifacts.elements.specification import (
    ELEMENT_SPECIFICATIONS,
    LoadContentSpec,
    MaterializeFileSpec,
    PublishContentSpec,
    PublishFileSpec,
    ReadContentSpec,
)
from plugins.codex.specification import CodexSpec


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("producer_kind", ["graph", "engineering_candidate"])
async def test_coding_candidate_survives_workspace_removal_and_api_restart(
    platform, application, codex_cli, tmp_path, monkeypatch, profile, producer_kind
):
    for spec in (*ELEMENT_SPECIFICATIONS, CodexSpec):
        application.elements.register_spec_class(spec)
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)
    compute, durable = tmp_path / "compute", tmp_path / "durable"
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    coding_key = credentials / "coding"
    coding_key.write_text("private-test-token")
    coding_key.chmod(0o600)
    access_file = credentials / "artifact"
    monkeypatch.setenv("PATH", str(codex_cli.parent) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FLAREWARD_WORKSPACE_ROOT", str(compute))
    monkeypatch.setenv("FLAREWARD_CODEX_API_KEY_FILE", str(coding_key))
    monkeypatch.setenv("FLAREWARD_ARTIFACT_ACCESS_FILE", str(access_file))
    monkeypatch.setenv("FLAREWARD_ARTIFACT_ALLOW_INSECURE", "true")
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="memory",
        authentication="development",
        development_user=platform.owner.id,
        artifact_directory=durable,
    )
    store = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.PROVIDER, rid="store"), type_key="artifact_store"
    )
    coder = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="coder"),
        type_key=CodexSpec.type_key,
        config={"model": "explicit-test"},
    )
    publisher = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="publish"),
        type_key=PublishFileSpec.type_key,
        config={"store": "$ref:store", "namespace": "project"},
    )
    materializer = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="restore"),
        type_key=MaterializeFileSpec.type_key,
        config={"store": "$ref:store"},
    )
    if producer_kind == "graph":
        producer = await publish(
            platform,
            "produce-artifact",
            GraphDefinition(
                resources=(store, coder, publisher),
                steps=(
                    OperationStep(
                        uid="code",
                        element=coder.key,
                        execution=ExecutionSelection(profile=profile),
                        inputs={"prompt": PathBinding(path=("input", "prompt"))},
                        outputs={"values": PathBinding(path=())},
                    ),
                    OperationStep(
                        uid="publish",
                        element=publisher.key,
                        execution=ExecutionSelection(profile=profile),
                        inputs={
                            "workspace": PathBinding(path=("values", "workspace")),
                            "path": LiteralBinding(value="answer.txt"),
                        },
                        outputs={"values": PathBinding(path=())},
                    ),
                ),
                edges={"code": ("publish",)},
                entry="code",
                exit="publish",
                outputs={"artifact": PathBinding(path=("values", "artifact"))},
            ),
        )
    else:
        resolver = ElementBundleResolver(application.elements)
        loader = ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="load"),
            type_key=LoadContentSpec.type_key,
            config={"store": "$ref:store"},
        )
        reader = ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="read"),
            type_key=ReadContentSpec.type_key,
        )
        content_publisher = publisher.model_copy(update={"type_key": PublishContentSpec.type_key})
        config = CodingFileCandidateConfig(
            coding=resolver.resolve(coder.key, (coder,)),
            loader=resolver.resolve(loader.key, (store, loader)),
            reader=resolver.resolve(reader.key, (reader,)),
            publisher=resolver.resolve(content_publisher.key, (store, content_publisher)),
            path="answer.txt",
            execution=ExecutionSelection(profile=profile),
            artifact_execution=ExecutionSelection(profile=profile),
        )
        producer = await publish(
            platform,
            "coding-candidate",
            ApplicationDefinition(
                implementation="coding_file_candidate",
                version="1",
                config=config.model_dump(mode="json"),
            ),
        )
    async with api_process(settings, tmp_path / "producer-api.log") as http:
        issued = await http.post(
            "/api/artifact-access",
            json={"scope": {"actions": ["read", "publish"], "namespaces": ["project"]}},
        )
        assert issued.status_code == 201, issued.text
        token = issued.json()["credential"]
        access_file.write_text(token)
        access_file.chmod(0o600)
        monkeypatch.setenv("FLAREWARD_ARTIFACT_ENDPOINT", str(http.base_url))
        inputs = (
            {"task": {"prompt": "durable candidate"}, "attempt": 0}
            if producer_kind == "engineering_candidate"
            else {"prompt": "durable candidate"}
        )
        result = await run(platform, producer, inputs, uuid4().hex)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        reference = (
            result.result["subject"]["identity"]
            if producer_kind == "engineering_candidate"
            else result.result["artifact"]
        )
        assert token not in result.model_dump_json() and token not in producer.model_dump_json()
    shutil.rmtree(compute)
    assert not compute.exists()
    bundle = ElementBundleResolver(application.elements).resolve(
        materializer.key, (store, materializer)
    )
    consumer = await publish(
        platform,
        "consume-artifact",
        ApplicationDefinition(
            implementation="placed_operation",
            version="1",
            config={"bundle": bundle.model_dump(mode="json"), "execution": {"profile": profile}},
        ),
    )
    async with api_process(settings, tmp_path / "consumer-api.log") as http:
        monkeypatch.setenv("FLAREWARD_ARTIFACT_ENDPOINT", str(http.base_url))
        restored = await run(
            platform, consumer, {"artifact": reference, "path": "restored/answer.txt"}, uuid4().hex
        )
        assert restored.phase == ExecutionPhase.COMPLETED, restored.failure
        assert restored.result["artifact"] == reference
        path = compute / restored.result["workspace"] / restored.result["path"]
        expected = "durable candidate"
        if producer_kind == "engineering_candidate":
            expected += "\n\nWrite the deliverable to workspace path: answer.txt"
        assert path.read_text() == expected
        assert token not in restored.model_dump_json()
