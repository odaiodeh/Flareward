"""Real resolution/compiler inspection is authorized, safe and free of persistence effects."""

import pytest
from mas.core.identity import Identity
from runengine.invocation.config import K8sRunnerConfig
from support.blueprint_http import library_api
from support.blueprints import inline_blueprint


@pytest.mark.parametrize(
    "selection,expected,environment,scope",
    [
        (None, "thread", None, "invocation"),
        ({}, "process", None, "invocation"),
        ({"environment": "coding"}, "isolated", "coding", "run"),
    ],
)
async def test_resolved_placement_validates_without_writes_or_secret_exposure(
    secret_settings, mongo_database, selection, expected, environment, scope
):
    settings = secret_settings.model_copy(
        update={
            "library": True,
            "execution_profiles": {
                **secret_settings.execution_profiles,
                "isolated": K8sRunnerConfig(
                    image="private-registry/receiver:fixture",
                    env={"PRIVATE_FIXTURE": "private-environment-value"},
                ),
            },
        }
    )
    async with library_api(settings, Identity.user("owner")) as http:
        spec = inline_blueprint("preview-private-value").model_dump(mode="json")
        spec["execution_profile"] = "process"
        spec["nodes"][0]["execution"] = {"profile": "thread"}
        spec["plan"][0]["execution"] = selection
        spec["environments"] = {"coding": "isolated"} if environment else {}
        before = {
            name: await mongo_database[name].find().to_list()
            for name in await mongo_database.list_collection_names()
        }
        preview = await http.post("/api/blueprints/draft/placement", json={"spec": spec})
        assert preview.status_code == 200, preview.text
        assert preview.json() == {
            "default_profile": "process",
            "environments": spec["environments"],
            "invocations": [
                {
                    "step_uid": "respond",
                    "category": "nodes",
                    "profile": expected,
                    "environment": environment,
                    "binding_scope": scope,
                }
            ],
        }
        assert "preview-private-value" not in preview.text
        assert "private-registry" not in preview.text
        assert "private-environment-value" not in preview.text
        assert {
            name: await mongo_database[name].find().to_list()
            for name in await mongo_database.list_collection_names()
        } == before
        stored = await http.post("/api/blueprints", json={"spec": spec})
        assert stored.status_code == 201, stored.text
        blueprint_id = stored.json()["blueprint_id"]
        assert (
            await http.get(f"/api/blueprints/{blueprint_id}/placement")
        ).json() == preview.json()
    async with library_api(settings, Identity.user("other")) as http:
        denied = await http.get(f"/api/blueprints/{blueprint_id}/placement")
        assert denied.status_code == 403
        assert "preview-private-value" not in denied.text


@pytest.mark.parametrize(
    "selection,environments",
    [
        ({"profile": "not-approved"}, {}),
        ({"environment": "coding"}, {"coding": "process"}),
        ({"environment": "missing"}, {}),
    ],
)
async def test_invalid_or_unsupported_placement_cannot_be_presented_as_valid(
    secret_settings, selection, environments
):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        spec = inline_blueprint().model_dump(mode="json")
        spec["plan"][0]["execution"] = selection
        spec["environments"] = environments
        preview = await http.post("/api/blueprints/draft/placement", json={"spec": spec})
        assert preview.status_code == 422, preview.text
