"""Real encrypted configuration storage, HTTP contracts, and native receiver construction."""

import hashlib
import json

import httpx
import pytest
from support.draft_configuration import (
    ELEMENT_SPECIFICATIONS,
    definition,
    unfinished_resource_graph,
)
from support.elements import element_registry
from support.secrets import secret_definition

from lumora.api.app import create_app
from lumora.bootstrap.platform import compose_platform
from lumora.resources.adapters.mongo.configuration_secrets import MongoConfigurationSecrets
from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_unfinished_resource_uses_encrypted_storage_and_normal_receiver_after_completion(
    secret_settings, mongo_database, profile
):
    elements = element_registry()
    for specification in ELEMENT_SPECIFICATIONS:
        elements.register_spec_class(specification)
    app = create_app(services_factory=lambda: compose_platform(secret_settings, elements=elements))
    root = definition(Identity.user("owner"), {}).model_copy(
        update={"implementation": unfinished_resource_graph(profile)}
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as http:
            saved = await http.put(
                "/api/programs/configured",
                json={"definition": root.model_dump(mode="json"), "expected_version": 0},
            )
            assert saved.status_code == 200 and "bundle-private" not in saved.text
            assert (
                await http.post("/api/programs/configured/revisions", json={"expected_version": 1})
            ).status_code == 422
            draft = saved.json()["definition"]
            draft["implementation"]["resources"][1]["config"]["endpoint"] = "constructed"
            completed = await http.put(
                "/api/programs/configured", json={"definition": draft, "expected_version": 1}
            )
            assert completed.status_code == 200, completed.text
            revision = await http.post(
                "/api/programs/configured/revisions", json={"expected_version": 2}
            )
            assert revision.status_code == 201, revision.text
            started = await http.post(
                "/api/executions",
                json={
                    "program": {
                        "program_id": "configured",
                        "revision": revision.json()["revision"],
                    },
                    "inputs": {"name": "ready"},
                },
            )
            assert started.status_code == 202, started.text
            result = await http.get(f"/api/executions/{started.json()['execution_id']}/result")
            assert result.json()["phase"] == "completed", result.text
            assert result.json()["result"] == {"answer": "typed:constructed:ready"}
    for collection in (
        mongo_database.program_drafts,
        mongo_database.program_revisions,
        mongo_database.program_executions,
        mongo_database.program_configuration_secrets,
    ):
        assert "bundle-private" not in json.dumps(await collection.find().to_list(), default=str)


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_secret_references_keep_old_revisions_and_payloads_private(
    secret_settings, mongo_database, profile
):
    app = create_app(
        services_factory=lambda: compose_platform(secret_settings, elements=element_registry())
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as http:
            version = 0
            for token in ("first-private-value", "second-private-value"):
                definition = secret_definition(profile, token)
                saved = await http.put(
                    "/api/programs/private-program",
                    json={
                        "definition": definition.model_dump(mode="json"),
                        "expected_version": version,
                    },
                )
                assert saved.status_code == 200, saved.text
                assert token not in saved.text
                version = saved.json()["version"]
                revision = await http.post(
                    "/api/programs/private-program/revisions", json={"expected_version": version}
                )
                assert revision.status_code == 201 and token not in revision.text, revision.text
            for number, token in enumerate(("first-private-value", "second-private-value"), 1):
                admitted = await http.post(
                    "/api/executions",
                    json={
                        "program": {"program_id": "private-program", "revision": number},
                        "execution_id": f"private-{number}",
                    },
                )
                assert admitted.status_code == 202, admitted.text
                result = await http.get(f"/api/executions/private-{number}/result")
                assert result.json()["phase"] == "completed", result.text
                assert result.json()["result"] == {
                    "digest": hashlib.sha256(token.encode()).hexdigest()
                }
    for collection in (
        mongo_database.program_drafts,
        mongo_database.program_revisions,
        mongo_database.program_executions,
        mongo_database.program_configuration_secrets,
    ):
        documents = await collection.find().to_list()
        assert documents
        encoded = json.dumps(documents, default=str)
        assert "first-private-value" not in encoded and "second-private-value" not in encoded
    values = await mongo_database.program_configuration_secrets.find().to_list()
    assert len(values) == 2 and all(value["value"].startswith("gAAAAA") for value in values)
    store = MongoConfigurationSecrets(
        mongo_database, FieldCipher(secret_settings.credential_encryption_key.get_secret_value())
    )
    with pytest.raises(PermissionError):
        await store.get(Identity.user("another-owner"), "lumora-secret:v1:" + values[0]["_id"])


@pytest.mark.parametrize("stage", ["construction", "execution"])
async def test_protected_failures_do_not_publish_credential_values(
    secret_settings, mongo_database, stage
):
    token = "private-error-token"
    app = create_app(
        services_factory=lambda: compose_platform(secret_settings, elements=element_registry())
    )
    async with app.router.lifespan_context(app):
        services = app.state.platform
        definition = secret_definition(
            "thread", token, fail=stage == "construction", fail_on_run=stage == "execution"
        )
        await services.programs.save(definition, definition.owner)
        revision = await services.programs.publish(
            definition.program_id,
            definition.owner,
            expected_version=(
                await services.programs.draft(definition.program_id, definition.owner)
            ).version,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as http:
            admitted = await http.post(
                "/api/executions", json={"program": revision.reference.model_dump(mode="json")}
            )
            result = await http.get(f"/api/executions/{admitted.json()['execution_id']}/result")
            assert result.json()["phase"] == "failed", result.text
            assert token not in result.text
            assert "failed" in result.json()["failure"]["message"].lower()
