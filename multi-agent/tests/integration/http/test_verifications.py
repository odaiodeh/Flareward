"""Human sessions cannot attest evidence; verifier credentials cannot become user sessions."""

import hashlib

import httpx
from fastapi import HTTPException
from inbound.http_api.app import create_app
from inbound.http_api.verification_auth import VerifierAuthenticator
from mas.application.verification.access_models import VerificationActor
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from outbound.mongo.verification_repository import MongoVerificationRepository
from support.verification import (
    VerificationClock,
    evidence_request,
    verification_authority,
    verification_policy,
    verification_request,
)


async def test_exact_subject_and_verifier_roles_survive_api_reconstruction(
    platform, mongo_database
):
    owner, clock = Identity.user("owner"), VerificationClock()
    credential = "test-verifier-credential-" + "x" * 32
    verifier_headers = {"Authorization": "Bearer " + credential, "X-Verification-Authority": "ci"}
    auth = VerifierAuthenticator(
        {
            "ci": (hashlib.sha256(credential.encode()).hexdigest(), verification_authority(owner)),
        }
    )

    async def human(request):
        name = request.headers.get("X-Human", "")
        if name not in {"owner", "other"}:
            raise HTTPException(401, "Human session required")
        return Identity.user(name)

    repository = MongoVerificationRepository(mongo_database)
    policies = {"release@1": verification_policy(owner)}
    service = VerificationService(repository, policies, clock=clock)
    app = create_app(
        platform.programs,
        platform.executions,
        human,
        verifications=service,
        authenticate_verifier=auth,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        request = verification_request()
        human_headers = {"X-Human": "owner"}
        assert (
            await http.post("/api/verifications", json=request.model_dump(mode="json"))
        ).status_code == 401
        created = await http.post(
            "/api/verifications", headers=human_headers, json=request.model_dump(mode="json")
        )
        assert created.status_code == 200, created.text
        assert created.headers["cache-control"] == "no-store"
        plan = (
            await service.inspect(
                created.json()["state"]["plan"]["plan_id"], VerificationActor(owner)
            )
        ).state.plan
        body = evidence_request(plan).model_dump(mode="json")
        assert (
            await http.post("/api/verification-evidence", headers=human_headers, json=body)
        ).status_code == 401
        assert (
            await http.post(
                "/api/verification-evidence",
                headers={**verifier_headers, "Authorization": "Bearer wrong"},
                json=body,
            )
        ).status_code == 401
        assert (
            await http.post(
                "/api/verifications", headers=verifier_headers, json=request.model_dump(mode="json")
            )
        ).status_code == 401
        assert (
            await http.get(f"/api/verifications/{plan.plan_id}", headers={"X-Human": "other"})
        ).status_code == 404
        changed = {
            **body,
            "subject": verification_request(digest="b" * 64).subject.model_dump(mode="json"),
        }
        assert (
            await http.post("/api/verification-evidence", headers=verifier_headers, json=changed)
        ).status_code == 409
        receipt = await http.post("/api/verification-evidence", headers=verifier_headers, json=body)
        assert receipt.status_code == 200 and receipt.json()["outcome"] == "pending"
        assert credential not in receipt.text
        assert (
            await http.post("/api/verification-evidence", headers=verifier_headers, json=body)
        ).json() == receipt.json()
        assert (
            await http.post(
                "/api/verification-evidence",
                headers=verifier_headers,
                json={**body, "verdict": "failed"},
            )
        ).status_code == 409
        assert (
            await http.post(
                "/api/verification-evidence",
                headers=verifier_headers,
                json={**body, "check": "security@1"},
            )
        ).status_code == 403

    restored = MongoVerificationRepository(mongo_database)
    app = create_app(
        platform.programs,
        platform.executions,
        human,
        verifications=VerificationService(restored, {}, clock=clock),
        authenticate_verifier=auth,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        read = await http.get(f"/api/verifications/{plan.plan_id}", headers=human_headers)
        assert read.status_code == 200 and read.json()["outcome"] == "pending"
        cancelled = await http.post(
            f"/api/verifications/{plan.plan_id}/cancel", headers=human_headers
        )
        assert cancelled.status_code == 200 and cancelled.json()["outcome"] == "cancelled"
    stored = await mongo_database.program_verifications.find_one({"_id": plan.plan_id})
    assert credential not in stored["data"]
