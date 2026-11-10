"""Actual Mongo-backed HTTP capability admission enforces independent root/policy/actions."""

import httpx
from fastapi import HTTPException
from support.execution_access import ExecutionAuthority
from support.verification import verification_policy, verification_request

from lumora.api.app import create_app
from lumora.services.identity.domain import Identity
from lumora.services.verification.access import VerificationAccessService
from lumora.services.verification.adapters.mongo.verification_access import (
    MongoVerificationAccessRepository,
)
from lumora.services.verification.adapters.mongo.verification_repository import (
    MongoVerificationRepository,
)
from lumora.services.verification.service import VerificationService


async def test_scoped_workflow_access_cannot_cross_roots_manage_grants_or_fall_back_to_human(
    platform,
    mongo_database,
):
    owner = Identity.user("owner")
    policies = {"release@1": verification_policy(owner)}
    repository = MongoVerificationAccessRepository(mongo_database)
    await repository.initialize()

    async def authenticate(request):
        name = request.headers.get("X-Human")
        if name not in {"owner", "other"}:
            raise HTTPException(401, "Human session required")
        request.state.authenticated_user = name
        return Identity.user(name)

    app = create_app(
        platform.programs,
        platform.executions,
        authenticate,
        verification_access=VerificationAccessService(
            repository, policies, execution_authority=ExecutionAuthority()
        ),
        verifications=VerificationService(MongoVerificationRepository(mongo_database), policies),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:

        async def issue(root, actions):
            response = await http.post(
                "/api/verification-access",
                headers={"X-Human": "owner"},
                json={
                    "scope": {
                        "root_execution_id": root,
                        "policies": ["release@1"],
                        "actions": actions,
                    },
                },
            )
            assert response.status_code == 201, response.text
            return response.json()

        first = await issue("first", ["create", "read", "cancel"])
        second = await issue("second", ["create", "read", "cancel"])
        credentials = [
            {"Authorization": "Bearer " + item["credential"]} for item in (first, second)
        ]
        request = verification_request().model_dump(mode="json")
        plans = []
        for credential in credentials:
            response = await http.post("/api/verifications", headers=credential, json=request)
            assert response.status_code == 200, response.text
            plans.append(response.json()["state"]["plan"])
        assert plans[0]["plan_id"] != plans[1]["plan_id"]
        assert (
            await http.get("/api/verifications/" + plans[1]["plan_id"], headers=credentials[0])
        ).status_code == 404
        assert (
            await http.post(
                "/api/verification-access",
                headers=credentials[0],
                json={"scope": first["grant"]["scope"]},
            )
        ).status_code == 401
        assert (
            await http.get(
                "/api/verification-access/self",
                headers={"X-Human": "owner", "Authorization": "Bearer invalid"},
            )
        ).status_code == 401
        readonly = await issue("first", ["read"])
        read_headers = {"Authorization": "Bearer " + readonly["credential"]}
        assert (
            await http.get("/api/verifications/" + plans[0]["plan_id"], headers=read_headers)
        ).status_code == 200
        assert (
            await http.post("/api/verifications", headers=read_headers, json=request)
        ).status_code == 403
        assert (
            await http.post(
                "/api/verifications/" + plans[0]["plan_id"] + "/cancel", headers=read_headers
            )
        ).status_code == 403
        assert (
            await http.delete(
                "/api/verification-access/" + first["grant"]["grant_id"],
                headers={"X-Human": "other"},
            )
        ).status_code == 404
        assert (
            await http.delete(
                "/api/verification-access/" + first["grant"]["grant_id"],
                headers={"X-Human": "owner"},
            )
        ).status_code == 204
        assert (
            await http.get("/api/verification-access/self", headers=credentials[0])
        ).status_code == 401
        stored = await mongo_database.verification_access_grants.find_one(
            {"_id": first["grant"]["grant_id"]}
        )
        assert first["credential"] not in stored["data"] and stored["revoked"]
