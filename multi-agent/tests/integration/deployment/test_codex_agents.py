"""Real Codex agents edit and test code in an explicitly selected remote environment."""

import json
import os
from contextlib import AsyncExitStack
from uuid import uuid4

import pytest
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.element_bundles import ResourceDefinition, ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import (
    GraphDefinition,
    OperationStep,
    PathBinding,
    ProgramDefinition,
)
from mas_plugins.coding.codex.identifiers import TYPE_KEY
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from support.deployment_backend import NetworkEndpoint
from support.http_programs import execute_program, publish_program
from support.resource_http import create_resource
from support.scenarios import resource
from support.server import api_process
from support.temporal import replay, worker_process
from temporalio.client import Client

from config.worker_settings import WorkerSettings


@pytest.fixture
async def coding_deployment(
    live_coding_key, remote_backend, deployment_host, secret_settings, tmp_path
):
    values = {
        "UNIFAI_CONFIGURATION_SECRETS": "false",
        "UNIFAI_CODEX_API_KEY": live_coding_key.get_secret_value(),
    }
    async with AsyncExitStack() as owned:
        target = await owned.enter_async_context(
            remote_backend.configured(
                values,
                (NetworkEndpoint("api.openai.com", 443, ("/usr/local/bin/codex",)),),
            )
        )
        target = target.model_copy(
            update={
                "env": {
                    **target.env,
                    "UNIFAI_CODEX_SANDBOX_MODE": "danger-full-access",
                    "UNIFAI_CODEX_API_KEY_FILE": (
                        target.env["UNIFAI_SECRETS_DIR"] + "/UNIFAI_CODEX_API_KEY"
                    ),
                }
            }
        )
        host = LocalHostConfig()
        if deployment_host == "temporal":
            host = TemporalHostConfig(
                endpoint=os.environ["UNIFAI_TEST_TEMPORAL_ENDPOINT"],
                task_queue="unifai-codex-" + uuid4().hex,
                invocation_timeout_seconds=180,
            )
        settings = secret_settings.model_copy(
            update={
                "host": host,
                "receiver_module": "bootstrap.receiver",
                "execution_profiles": {"coding": target},
                "default_execution_profile": "coding",
                "library": True,
                "element_modules": ("support.coding",),
                "reconcile_interval": 0.05,
            }
        )
        worker = None
        native = None
        if deployment_host == "temporal":
            worker = WorkerSettings.model_validate(
                {
                    **settings.model_dump(mode="python"),
                    "environment_sqlite": tmp_path / "env.sqlite",
                }
            )
            await owned.enter_async_context(worker_process(worker, tmp_path / "worker.log"))
            native = await Client.connect(host.endpoint)
        http = await owned.enter_async_context(api_process(settings, tmp_path / "api.log"))
        yield http, remote_backend, live_coding_key, native, worker


@pytest.mark.e2e
@pytest.mark.llm_integration
async def test_codex_steps_share_files_and_keep_credentials_out_of_published_data(
    coding_deployment,
    tmp_path,
):
    http, backend, api_key, native, worker = coding_deployment
    resources = []
    for name, instructions in (
        (
            "write",
            "Create a tiny Python file calculation.py defining add(a, b) returning a + b. "
            "Do not read any parent or other directories. Reply briefly when written.",
        ),
        (
            "verify",
            "Use calculation.py already in this workspace. Run Python to assert add(20, 22) == 42. "
            "Create verified.txt containing exactly 42 after the assertion passes. "
            "Do not read other directories. Reply only VERIFIED_42 after running the assertion.",
        ),
    ):
        saved = await create_resource(
            http,
            ResourceCategory.OPERATION,
            TYPE_KEY,
            name,
            {
                "model": "gpt-5.4-nano",
                "instructions": instructions,
                "workspace_mode": "shared",
                "max_commands": 4,
                "timeout_seconds": 60,
            },
        )
        document = await http.get(f"/api/resources/{saved}")
        assert document.status_code == 200, document.text
        stored = document.json()
        resources.append(
            ResourceDefinition(
                key=ResourceKey(category=ResourceCategory.OPERATION, rid=saved),
                type_key=TYPE_KEY,
                config=stored["cfg_dict"],
            )
        )
    evidence = resource("evidence", category=ResourceCategory.OPERATION, type_key="coding_evidence")
    # Kubernetes owns a retained pod; OpenShell's fixture owns its pre-provisioned sandbox.
    owned_environment = backend.name == "k8s"
    selection = (
        ExecutionSelection(environment="coding")
        if owned_environment
        else ExecutionSelection(profile="coding")
    )
    graph = GraphDefinition(
        resources=(*resources, evidence),
        steps=tuple(
            OperationStep(
                uid=name,
                element=item.key,
                execution=selection,
                inputs={"workspace": PathBinding(path=("values", "workspace"))}
                if name == "evidence"
                else {"prompt": PathBinding(path=("user_prompt",))},
                outputs={"values": PathBinding(path=())},
            )
            for name, item in zip(
                ("write", "verify", "evidence"), (*resources, evidence), strict=True
            )
        ),
        edges={"write": ("verify",), "verify": ("evidence",)},
        entry="write",
        exit="evidence",
        environments={"coding": "coding"} if owned_environment else {},
        inputs={"user_prompt": PathBinding(path=("task",))},
        outputs={
            "answer": PathBinding(path=("values", "content")),
            "coding": PathBinding(path=("values",)),
            "evidence": PathBinding(path=("values", "evidence")),
        },
    )
    definition = ProgramDefinition(
        program_id="coding-workflow",
        name="Coding workflow",
        owner=Identity.user("owner"),
        implementation=graph,
    )
    # Saved resource configurations are frozen into the published program revision.
    reference = await publish_program(http, definition)
    execution = await execute_program(
        http, reference, uuid4().hex, {"task": "Write and verify addition."}
    )
    assert execution["phase"] == "completed", json.dumps(execution.get("failure"))
    assert "VERIFIED_42" in execution["result"]["answer"]
    proof = execution["result"]["evidence"]
    assert proof["verified"] == "42" and "def add" in proof["source"]
    assert proof["system"] == "Linux" and proof["namespace"] == backend.namespace
    assert proof["image_marker"] == "unifai-platform-e2e-v1"
    assert execution["result"]["coding"]["commands"] > 0
    assert execution["result"]["coding"]["usage"]["input_tokens"] > 0
    revision = await http.get(
        f"/api/programs/{reference.program_id}/revisions/{reference.revision}"
    )
    assert revision.status_code == 200, revision.text
    # Never let assertion introspection print a real credential on regression.
    if any(
        api_key.get_secret_value() in value
        for value in (revision.text, json.dumps(execution), (tmp_path / "api.log").read_text())
    ):
        pytest.fail(
            "Private provider credential appeared in public data or API logs", pytrace=False
        )
    if native is not None:
        await replay(native, worker, execution["context"]["engine_handle"])
    if owned_environment:
        await backend.assert_clean()
    # configured() owns the pre-existing environment and deletes it on context exit.
