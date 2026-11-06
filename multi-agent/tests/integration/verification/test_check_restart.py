"""External acknowledgement loss survives actual API process shutdown and restart."""

import pytest
from mas.core.identity import Identity
from support.check_api import check_api_settings
from support.check_runs import source_request
from support.github_checks import report_archive
from support.server import api_process


@pytest.mark.parametrize("mode", ["reconcile", "reports", "manual-resolution"])
async def test_api_restart_reconciles_an_accepted_dispatch_without_a_second_effect(
    mongo_database, redis_uri, tmp_path, mode
):
    owner = Identity.user("ci-owner")
    settings = check_api_settings(
        owner,
        mongo_database.name,
        redis_uri,
        development=True,
        artifact_directory=tmp_path / "reports" if mode != "reconcile" else None,
    )
    logs = (tmp_path / "before.log", tmp_path / "after.log")
    async with api_process(settings, logs[0], factory="support.check_api:create_app") as http:
        created = await http.post(
            "/api/verifications", json=source_request().model_dump(mode="json")
        )
        assert created.status_code == 200, created.text
        plan_id = created.json()["state"]["plan"]["plan_id"]
        response = await http.post(
            "/api/verification-checks", json={"plan_id": plan_id, "runner": "github@1"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "uncertain"
        intent_id = response.json()["intent_id"]
    await mongo_database.fixture_github_runs.update_one(
        {"_id": 1001}, {"$set": {"run.status": "completed", "run.conclusion": "success"}}
    )
    async with api_process(settings, logs[1], factory="support.check_api:create_app") as http:
        if mode == "manual-resolution":
            current = await http.get("/api/verification-checks/" + intent_id)
            assert current.status_code == 200, current.text
            resolution = {
                "key": "attach-existing",
                "expected_revision": current.json()["revision"],
                "external_id": "github-actions:example/product:1001:1",
                "reason": "Confirmed the provider job after losing its acknowledgement",
            }
            resolved = await http.post(
                f"/api/verification-checks/{intent_id}/resolve", json=resolution
            )
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["resolution"]["issued_by"]["id"] == owner.id
            assert (
                await http.post(f"/api/verification-checks/{intent_id}/resolve", json=resolution)
            ).json() == resolved.json()
        reconciled = await http.post(f"/api/verification-checks/{intent_id}/refresh")
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["evidence_recorded"] is True
        view = await http.get("/api/verifications/" + plan_id)
        assert view.json()["outcome"] == "accepted"
        reports = view.json()["state"]["evidence"][0]["reports"]
        assert bool(reports) == (mode != "reconcile")
        assert (
            await http.post(
                "/api/verification-checks", json={"plan_id": plan_id, "runner": "github@1"}
            )
        ).json() == reconciled.json()
        assert await mongo_database.fixture_github_runs.count_documents({}) == 1
    if mode != "reconcile":
        await mongo_database.fixture_github_runs.delete_many({})
        await mongo_database.fixture_github_artifacts.delete_many({})
        async with api_process(
            settings,
            tmp_path / "archive-after-retention.log",
            factory="support.check_api:create_app",
        ) as http:
            artifact_id = reports[0]["content"]["artifact_id"]
            downloaded = await http.get(f"/api/artifacts/{artifact_id}/content")
            assert downloaded.status_code == 200, downloaded.text
            assert downloaded.content == report_archive()
            assert (await http.post(f"/api/verification-checks/{intent_id}/refresh")).json()[
                "evidence_recorded"
            ] is True
    assert all(
        settings.github_checks["github@1"].token.get_secret_value() not in log.read_text()
        for log in logs
    )
