"""The API renews a short workflow lease during a real human wait, without replacing its token."""

import asyncio
from datetime import UTC, datetime

from support.credential_renewals import retired_credential
from support.review_api import review_api, review_settings
from support.review_programs import review_definition

from lumora.services.access.credentials import OpaqueCredentials
from lumora.services.identity.domain import Identity
from lumora.services.reviews.access import ReviewGrant, StoredReviewGrant
from lumora.services.reviews.adapters.mongo.reviews import MongoReviewAccessRepository
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS


async def test_short_grant_survives_original_expiry_during_native_human_wait(
    application, mongo_database, redis_uri, tmp_path
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    owner = Identity.user("renewal-owner")
    settings = review_settings(owner, mongo_database.name, redis_uri).model_copy(
        update={"reconcile_interval": 0.05}
    )
    async with review_api(
        owner,
        mongo_database.name,
        redis_uri,
        tmp_path,
        settings=settings,
        ttl_seconds=6,
        renewable_for_seconds=24,
    ) as api:
        program = await api.publish("renewing-review", review_definition(application.elements))
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": api.root,
                "program": program.reference.model_dump(mode="json"),
                "inputs": {"subject": "exact-candidate"},
            },
        )
        assert started.status_code == 202, started.text
        review = await api.pending()
        extended = api.grant
        async with asyncio.timeout(15):
            while (
                datetime.now(UTC) <= api.grant.expires_at
                or extended.expires_at == api.grant.expires_at
            ):
                response = await api.http.get("/api/review-access/self", headers=api.client)
                assert response.status_code == 200, response.text
                assert api.credential.get_secret_value() not in response.text
                extended = ReviewGrant.model_validate(response.json())
                await asyncio.sleep(0.05)
        assert extended.scope == api.grant.scope and extended.issued_at == api.grant.issued_at
        assert extended.expires_at <= extended.renewal.renewable_until
        response = await api.http.post(
            f"/api/reviews/{review.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "reviewed-after-original-expiry",
                "expected_revision": review.revision,
                "decision": "approve",
                "data": {"feedback": "Exact candidate reviewed"},
            },
        )
        assert response.status_code == 200, response.text
        result = await api.http.get(f"/api/executions/{api.root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
        assert (
            await api.http.get("/api/review-access/self", headers=api.client)
        ).status_code == 401
        retired = await retired_credential(
            MongoReviewAccessRepository(mongo_database), api.grant.grant_id
        )
        assert retired.scope == api.grant.scope and retired.issued_at == api.grant.issued_at
        document = await mongo_database.review_access_grants.find_one({"_id": api.grant.grant_id})
        stored = StoredReviewGrant.model_validate_json(document["data"])
        assert stored.secret_sha256 == OpaqueCredentials.digest(api.credential.get_secret_value())
