"""Real native review execution, assigned human sessions and shared operation receivers."""

import asyncio
import json

import pytest
from pydantic import SecretStr
from support.credential_renewals import retired_credential
from support.review_api import review_api
from support.review_programs import review_definition, review_graph

from lumora.programs.domain.models import CustomCoordinatorDefinition
from lumora.services.identity.domain import Identity
from lumora.services.reviews.adapters.mongo.reviews import MongoReviewAccessRepository
from lumora.services.reviews.domain.models import ReviewRecord
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("parent", ["graph", "code"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
@pytest.mark.parametrize("managed_delivery", [False, True])
async def test_native_workflow_resumes_only_from_the_assigned_human_decision(
    application, mongo_database, redis_uri, tmp_path, profile, parent, decision, managed_delivery
):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    async with review_api(
        Identity.user("review-owner"),
        mongo_database.name,
        redis_uri,
        tmp_path,
        managed_delivery=managed_delivery,
    ) as api:
        review_program = await api.publish(
            "review", review_definition(application.elements, profile)
        )
        definition = (
            review_graph(review_program.reference)
            if parent == "graph"
            else CustomCoordinatorDefinition(
                implementation="composed", version="1", children={"greet": review_program.reference}
            )
        )
        workflow = await api.publish("workflow", definition)
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": api.root,
                "program": workflow.reference.model_dump(mode="json"),
                "inputs": {"subject": {"candidate": "exact-candidate"}},
            },
        )
        assert started.status_code == 202, started.text
        review = await api.pending()
        assert review.status == "pending" and review.execution_id != api.root
        assert review.specification.subject == {"subject": {"candidate": "exact-candidate"}}
        review_path = f"/api/executions/{api.root}/reviews"
        owned = await api.http.get(review_path, headers=api.human)
        assert owned.status_code == 200 and [
            value["review_id"] for value in owned.json()["reviews"]
        ] == [review.review_id]
        assert (await api.http.get(review_path, headers=api.reviewer)).json()["reviews"] == []
        assert (
            await api.http.get(review_path, headers={**api.human, **api.client})
        ).status_code == 401
        response = {
            "key": "human-choice",
            "expected_revision": review.revision,
            "decision": decision,
            "data": {"feedback": "Examined the exact candidate"},
        }
        path = f"/api/reviews/{review.review_id}/responses"
        assert (await api.http.post(path, headers=api.human, json=response)).status_code == 404
        assert (
            await api.http.post(path, headers={**api.reviewer, **api.client}, json=response)
        ).status_code == 401
        assert (
            await api.http.post(
                path, headers=api.reviewer, json={**response, "data": {"feedback": 7}}
            )
        ).status_code == 422
        assert (
            await api.http.post(
                f"/api/executions/{api.root}/messages",
                headers=api.human,
                json={"name": review.message_name, "data": {"decision": "approve"}},
            )
        ).status_code == 403
        accepted = await api.http.post(path, headers=api.reviewer, json=response)
        assert accepted.status_code == 200, accepted.text
        assert (await api.http.post(path, headers=api.reviewer, json=response)).json()[
            "response"
        ] == accepted.json()["response"]
        conflict = await api.http.post(
            path,
            headers=api.reviewer,
            json={**response, "decision": "reject" if decision == "approve" else "approve"},
        )
        assert conflict.status_code == 409, conflict.text
        result = await api.http.get(f"/api/executions/{api.root}/result", headers=api.human)
        assert result.status_code == 200, result.text
        assert result.json()["phase"] == "completed", result.text
        output = result.json()["result"]
        if parent == "graph":
            output = output["result"]
        assert output["reason"] == "resolved"
        assert output["review"]["response"]["decision"] == decision
        assert output["review"]["response"]["issued_by"]["id"] == "reviewer"
        assert (
            api.credential.get_secret_value() not in json.dumps(result.json()) + api.log.read_text()
        )
        retired = await retired_credential(
            MongoReviewAccessRepository(mongo_database), api.grant.grant_id
        )
        assert retired.model_copy(update={"revoked": False}) == api.grant
        if managed_delivery:
            async with asyncio.timeout(10):
                while True:
                    material = await mongo_database.workflow_credential_material.find_one({})
                    if material["retired"] and not material["cleanup_pending"]:
                        break
                    await asyncio.sleep(0.05)
            assert "credential" not in material
            assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
            assert not list(api.directory.iterdir())


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_managed_roots_share_delivery_without_sharing_authority_or_cleanup(
    application, mongo_database, redis_uri, tmp_path, profile
):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    async with review_api(
        Identity.user("review-owner"),
        mongo_database.name,
        redis_uri,
        tmp_path,
        managed_delivery=True,
    ) as api:
        review_program = await api.publish(
            "review", review_definition(application.elements, profile)
        )
        workflow = await api.publish("workflow", review_graph(review_program.reference))
        other_root = api.root + "-independent"
        issued = await api.http.post(
            "/api/review-access",
            headers={**api.human, "Idempotency-Key": "independent-root"},
            json={
                "scope": {
                    **api.grant.scope.model_dump(mode="json"),
                    "root_execution_id": other_root,
                }
            },
        )
        assert issued.status_code == 201, issued.text
        other_secret = SecretStr(issued.json()["credential"])
        other_client = {"Authorization": "Bearer " + other_secret.get_secret_value()}
        started = await asyncio.gather(
            *(
                api.http.post(
                    "/api/executions",
                    headers=api.human,
                    json={
                        "execution_id": root,
                        "program": workflow.reference.model_dump(mode="json"),
                        "inputs": {"subject": {"candidate": root}},
                    },
                )
                for root in (api.root, other_root)
            )
        )
        assert all(response.status_code == 202 for response in started)
        async with asyncio.timeout(30):
            while True:
                inbox = await api.http.get("/api/reviews/inbox", headers=api.reviewer)
                assert inbox.status_code == 200, inbox.text
                reviews = {
                    row.root_execution_id: row
                    for value in inbox.json()["reviews"]
                    if (row := ReviewRecord.model_validate(value)).status == "pending"
                }
                if set(reviews) == {api.root, other_root}:
                    break
                await asyncio.sleep(0.05)
        assert (
            await api.http.get(f"/api/reviews/{reviews[api.root].review_id}", headers=other_client)
        ).status_code == 404
        directory = tmp_path / "managed-workflow-access"
        assert len(list(directory.rglob("*.json"))) == 2
        cancelled = await api.http.post(f"/api/executions/{api.root}/cancel", headers=api.human)
        assert cancelled.status_code == 202, cancelled.text
        result = await api.http.get(f"/api/executions/{api.root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "cancelled", result.text
        async with asyncio.timeout(10):
            while len(list(directory.rglob("*.json"))) != 1:
                await asyncio.sleep(0.05)
        assert (
            await api.http.get("/api/review-access/self", headers=api.client)
        ).status_code == 401
        assert (
            await api.http.get("/api/review-access/self", headers=other_client)
        ).status_code == 200
        remaining = reviews[other_root]
        accepted = await api.http.post(
            f"/api/reviews/{remaining.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "independent-approval",
                "expected_revision": remaining.revision,
                "decision": "approve",
                "data": {"feedback": "Reviewed the independent candidate"},
            },
        )
        assert accepted.status_code == 200, accepted.text
        result = await api.http.get(f"/api/executions/{other_root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["result"]["review"]["response"]["decision"] == "approve"
        async with asyncio.timeout(10):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert not list(directory.rglob("*.json")) and not list(api.directory.iterdir())
        assert all(
            secret not in result.text + api.log.read_text()
            for secret in (api.credential.get_secret_value(), other_secret.get_secret_value())
        )


@pytest.mark.parametrize("mode", ["expired", "cancelled", "superseded"])
async def test_native_review_lifecycle_never_turns_closed_work_into_approval(
    application, mongo_database, redis_uri, tmp_path, mode
):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    async with review_api(
        Identity.user("review-owner"), mongo_database.name, redis_uri, tmp_path
    ) as api:
        definition = review_definition(application.elements)
        if mode == "expired":
            definition.config["template"]["timeout_seconds"] = 1
        program = await api.publish("lifecycle-review", definition)
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": api.root,
                "program": program.reference.model_dump(mode="json"),
                "inputs": {"candidate": "exact-candidate"},
            },
        )
        assert started.status_code == 202, started.text
        review = await api.pending()
        if mode == "cancelled":
            assert (
                await api.http.post(f"/api/executions/{api.root}/cancel", headers=api.human)
            ).status_code == 202
        elif mode == "superseded":
            replacement = await api.http.post(
                "/api/reviews",
                headers=api.client,
                json={
                    "key": "replacement",
                    "execution_id": review.execution_id,
                    "policy": review.policy,
                    "specification": review.specification.model_dump(mode="json"),
                },
            )
            assert replacement.status_code == 200, replacement.text
            closed = await api.http.post(
                f"/api/reviews/{review.review_id}/close",
                headers=api.client,
                json={
                    "review_id": review.review_id,
                    "expected_revision": review.revision,
                    "superseded_by": replacement.json()["review_id"],
                },
            )
            assert closed.status_code == 200, closed.text
        result = await api.http.get(f"/api/executions/{api.root}/result", headers=api.human)
        assert result.status_code == 200, result.text
        assert result.json()["phase"] == ("cancelled" if mode == "cancelled" else "completed"), (
            result.text
        )
        async with asyncio.timeout(10):
            while True:
                current = await api.http.get(
                    f"/api/reviews/{review.review_id}", headers=api.reviewer
                )
                assert current.status_code == 200, current.text
                if current.json()["status"] == mode:
                    break
                await asyncio.sleep(0.05)
        assert current.json()["response"] is None
        late = await api.http.post(
            f"/api/reviews/{review.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "late",
                "expected_revision": review.revision,
                "decision": "approve",
                "data": {"feedback": "Too late"},
            },
        )
        assert late.status_code == 409, late.text
        wrong_scope = await api.http.post(
            "/api/review-access",
            headers=api.human,
            json={
                "scope": {
                    "root_execution_id": "different-root",
                    "policies": ["release@1"],
                    "actions": ["read"],
                }
            },
        )
        assert wrong_scope.status_code == 201, wrong_scope.text
        other = await api.publish(
            "other-root", CustomCoordinatorDefinition(implementation="waiting", version="1")
        )
        started_other = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": "different-root",
                "program": other.reference.model_dump(mode="json"),
                "inputs": {},
            },
        )
        assert started_other.status_code == 202, started_other.text
        assert (
            await api.http.get(
                f"/api/reviews/{review.review_id}",
                headers={"Authorization": "Bearer " + wrong_scope.json()["credential"]},
            )
        ).status_code == 404
        assert (
            await api.http.post("/api/executions/different-root/cancel", headers=api.human)
        ).status_code == 202
        assert (
            await api.http.get("/api/executions/different-root/result", headers=api.human)
        ).json()["phase"] == "cancelled"
        assert (await api.http.get("/api/reviews/inbox", headers=api.client)).status_code == 401
