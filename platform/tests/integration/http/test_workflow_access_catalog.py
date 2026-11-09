"""Native catalog reads preserve human ownership and cannot allocate grant material."""

from support.managed_access import managed_access_api


async def test_native_workflow_access_catalog_is_human_owner_scoped_and_read_only(
    mongo_database, redis_uri, tmp_path
):
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        response = await api.http.get("/api/catalog/workflow-access", headers=api.human)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "private, no-store"
        assert {item["purpose"] for item in response.json()} == {"review@1", "verification@1"}
        assert (
            await api.http.get("/api/catalog/workflow-access", headers=api.reviewer)
        ).json() == []
        assert (
            await api.http.get(
                "/api/catalog/workflow-access",
                headers={**api.human, "Authorization": "Bearer invalid"},
            )
        ).status_code == 401
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        assert await mongo_database.review_access_grants.count_documents({}) == 0
        assert await mongo_database.verification_access_grants.count_documents({}) == 0
        assert not list((tmp_path / "managed-workflow-access").glob("*.json"))
