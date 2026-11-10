"""Saved resource selections become protected revisions through native HTTP and Mongo."""

import pytest
from support.blueprint_http import library_api
from support.http_programs import execute_program
from support.library_resources import seed_operation_resources, seed_private_agent_resources
from support.resource_snapshots import saved_resource_graph

from lumora.programs.domain.models import (
    ElementStep,
    GraphDefinition,
    PathBinding,
    ProgramDefinition,
    ProgramRef,
)
from lumora.resources.adapters.mongo.configuration_secrets import MongoConfigurationSecrets
from lumora.resources.domain.bundles import ResourceKey
from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_selected_operation_closure_is_frozen_and_updates_require_explicit_adoption(
    secret_settings, application, profile
):
    owner = Identity.user("owner")
    async with library_api(
        secret_settings.model_copy(update={"library": True}), owner, elements=application.elements
    ) as http:
        root, middle, _ = await seed_operation_resources(http, profile=profile)
        graph = saved_resource_graph(profile)
        step = graph.steps[0].model_copy(
            update={"element": ResourceKey(category="operations", rid=root["rid"])}
        )
        graph = graph.model_copy(update={"steps": (step,)})
        definition = ProgramDefinition(
            program_id="selected", name="Selected work", owner=owner, implementation=graph
        ).model_dump(mode="json")
        selection = {"source": root["source"]}
        saved = await http.put(
            "/api/programs/selected",
            json={
                "definition": definition,
                "expected_version": 0,
                "resource_selections": [selection],
            },
        )
        assert saved.status_code == 200, saved.text
        frozen = saved.json()
        assert len(frozen["definition"]["implementation"]["resources"]) == 3
        published = await http.post(
            "/api/programs/selected/revisions", json={"expected_version": frozen["version"]}
        )
        assert published.status_code == 201, published.text
        reference = {"program_id": "selected", "revision": published.json()["revision"]}
        changed = await http.put(
            "/api/resources/" + middle["rid"],
            json={
                "config": {**middle["cfg_dict"], "value": "changed"},
                "expected_version": middle["version"],
            },
        )
        assert changed.status_code == 200, changed.text
        original = await execute_program(
            http, ProgramRef.model_validate(reference), "original", {"name": "first"}
        )
        assert original["result"] == {"answer": "typed:saved-middle:first"}
        preserved = await http.put(
            "/api/programs/selected",
            json={"definition": frozen["definition"], "expected_version": frozen["version"]},
        )
        assert preserved.status_code == 200, preserved.text
        version = preserved.json()["version"]
        conflict = await http.put(
            "/api/programs/selected",
            json={
                "definition": preserved.json()["definition"],
                "expected_version": version,
                "resource_selections": [selection],
            },
        )
        assert conflict.status_code == 409, conflict.text
        adopted = await http.put(
            "/api/programs/selected",
            json={
                "definition": preserved.json()["definition"],
                "expected_version": version,
                "resource_selections": [{**selection, "adoption": "replace"}],
            },
        )
        assert adopted.status_code == 200, adopted.text
        newer = await http.post(
            "/api/programs/selected/revisions", json={"expected_version": adopted.json()["version"]}
        )
        assert newer.status_code == 201, newer.text
        new_result = await execute_program(
            http,
            ProgramRef(program_id="selected", revision=newer.json()["revision"]),
            "adopted",
            {"name": "second"},
        )
        assert new_result["result"] == {"answer": "typed:changed:second"}
        old_result = await execute_program(
            http, ProgramRef.model_validate(reference), "pinned", {"name": "third"}
        )
        assert old_result["result"] == {"answer": "typed:saved-middle:third"}
        root_update = await http.put(
            "/api/resources/" + root["rid"],
            json={
                "config": {**root["cfg_dict"], "prefix": "new:"},
                "expected_version": root["version"],
            },
        )
        assert root_update.status_code == 200, root_update.text
        stale = await http.put(
            "/api/programs/stale",
            json={
                "definition": {**definition, "program_id": "stale"},
                "expected_version": 0,
                "resource_selections": [selection],
            },
        )
        assert stale.status_code == 409, stale.text
        assert (await http.get("/api/programs/stale")).status_code == 404


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("team", [False, True])
async def test_selected_agent_resolves_authorized_builtin_overlay_without_exporting_secrets(
    secret_settings, mongo_database, profile, team
):
    owner = Identity.team("team") if team else Identity.user("owner")
    cipher = FieldCipher(secret_settings.credential_encryption_key.get_secret_value())
    await seed_private_agent_resources(mongo_database, owner, cipher)
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, owner) as http:
        agent = await http.get("/api/resources/library-agent")
        assert agent.status_code == 200, agent.text
        graph = GraphDefinition(
            steps=(
                ElementStep(
                    uid="respond",
                    element=ResourceKey(category="nodes", rid="library-agent"),
                    execution={"profile": profile},
                ),
            ),
            entry="respond",
            exit="respond",
            inputs={"user_prompt": PathBinding(path=("prompt",))},
            outputs={"answer": PathBinding(path=("nodes_output", "respond"))},
        )
        definition = ProgramDefinition(
            program_id="private-agent", name="Private agent", owner=owner, implementation=graph
        )
        saved = await http.put(
            "/api/programs/private-agent",
            json={
                "definition": definition.model_dump(mode="json"),
                "expected_version": 0,
                "resource_selections": [{"source": agent.json()["source"]}],
            },
        )
        assert saved.status_code == 200, saved.text
        assert (
            "caller-private-value" not in saved.text and "admin-private-default" not in saved.text
        )
        model = next(
            value
            for value in saved.json()["definition"]["implementation"]["resources"]
            if value["key"]["rid"] == "library-model"
        )
        store = MongoConfigurationSecrets(mongo_database, cipher)
        assert (
            await store.get(owner, model["config"]["api_key"])
        ).get_secret_value() == "caller-private-value"
        revision = await http.post(
            "/api/programs/private-agent/revisions",
            json={"expected_version": saved.json()["version"]},
        )
        assert revision.status_code == 201, revision.text
        result = await execute_program(
            http,
            ProgramRef(program_id="private-agent", revision=revision.json()["revision"]),
            "selected-agent-run",
            {"prompt": "saved selection"},
        )
        assert result["phase"] == "completed", result
        assert result["result"] == {"answer": "Mock echo: saved selection"}
    other = Identity.user("other")
    async with library_api(settings, other) as http:
        denied = await http.put(
            "/api/programs/foreign",
            json={
                "definition": definition.model_copy(
                    update={"program_id": "foreign", "owner": other}
                ).model_dump(mode="json"),
                "expected_version": 0,
                "resource_selections": [{"source": agent.json()["source"]}],
            },
        )
        assert denied.status_code == 404, denied.text
