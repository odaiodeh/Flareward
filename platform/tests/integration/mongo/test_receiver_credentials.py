"""Actual encrypted stores and receiver credentials across thread/process dispatch."""

import asyncio
import json
import os

import pytest
from cryptography.fernet import Fernet
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.credentials import CredentialSpec
from support.elements import element_registry
from support.scenarios import resource

from lumora.bootstrap.credentials import receiver_auth
from lumora.bootstrap.platform import compose_platform
from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.executions.models import StartExecution
from lumora.programs.domain.models import (
    ElementStep,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
    ProgramDefinition,
)
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.auth.credentials.models import StoredCredential
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_native_receiver_uses_human_credentials_for_team_owned_child(
    mongo_database, monkeypatch, profile
):
    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setenv("LUMORA_CREDENTIALS", "mongo")
    monkeypatch.setenv("LUMORA_INTERACTIONS", "disabled")
    monkeypatch.setenv("LUMORA_MONGO_URI", os.environ["LUMORA_TEST_MONGO_URI"])
    monkeypatch.setenv("LUMORA_MONGO_DATABASE", mongo_database.name)
    monkeypatch.setenv("LUMORA_CREDENTIAL_ENCRYPTION_KEY", encryption_key)
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        authentication="development",
        development_user="member",
        execution_profiles={
            "thread": ThreadRunnerConfig(),
            "process": ProcessRunnerConfig(max_workers=1),
        },
        default_execution_profile="thread",
    )
    async with receiver_auth(settings) as auth:
        for user, token in (("member", "member-secret"), ("team", "wrong-secret")):
            await asyncio.to_thread(
                auth.save_credential,
                StoredCredential(
                    user_id=user,
                    server_identifier="test-issuer",
                    access_token=token,
                    scheme_type="api_key",
                ),
            )
        sealed = auth.seal_token("browser-secret")
        assert sealed != "browser-secret"
        assert auth.unseal_token(sealed) == "browser-secret"
    stored = await mongo_database.credentials.find_one({"user_id": "member"})
    assert stored["access_token"].startswith("gAAAAA")
    assert "member-secret" not in json.dumps(stored, default=str)
    elements = element_registry()
    elements.register_spec_class(CredentialSpec)
    owner = Identity.team("team")
    async with compose_platform(settings, elements=elements) as services:
        node = resource(
            "credential", category=ResourceCategory.NODE, type_key="platform_credential"
        )
        leaf = ProgramDefinition(
            program_id="credential-leaf",
            name="Credential consumer",
            owner=owner,
            implementation=GraphDefinition(
                steps=(
                    ElementStep(
                        uid="credential",
                        element=node.key,
                        execution=ExecutionSelection(profile=profile),
                    ),
                ),
                resources=(node,),
                entry="credential",
                exit="credential",
                outputs={"answer": PathBinding(path=("output",))},
            ),
        )
        await services.programs.save(leaf, owner)
        revision = await services.programs.publish(
            leaf.program_id,
            owner,
            expected_version=(await services.programs.draft(leaf.program_id, owner)).version,
        )
        parent = ProgramDefinition(
            program_id="credential-parent",
            name="Team program",
            owner=owner,
            implementation=GraphDefinition(
                steps=(
                    ProgramCallStep(
                        uid="child",
                        program=revision.reference,
                        outputs={"output": PathBinding(path=("answer",))},
                    ),
                ),
                entry="child",
                exit="child",
                outputs={"answer": PathBinding(path=("output",))},
            ),
        )
        await services.programs.save(parent, owner)
        revision = await services.programs.publish(
            parent.program_id,
            owner,
            expected_version=(await services.programs.draft(parent.program_id, owner)).version,
        )
        record = await services.executions.start(
            StartExecution(program=revision.reference, execution_id="root", session_id="chat"),
            owner,
            credential_user_id="member",
        )
        async with asyncio.timeout(10):
            result = await services.executions.result(record.execution_id, owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        received = json.loads(result.result["answer"])
        assert received["headers"] == {"Authorization": "Bearer member-secret"}
        context = received["context"]
        assert context["identity"]["id"] == "team"
        assert context["parent_execution_id"] == context["root_execution_id"] == "root"
        assert context["execution_id"] != "root" and context["session_id"] == "chat"
    snapshot = await MongoExecutionRepository(mongo_database).get_prepared("root")
    # Only deterministic test results expose the fake token; prepared work contains no credentials.
    assert "member-secret" not in snapshot.payload_json
    assert encryption_key not in snapshot.payload_json
