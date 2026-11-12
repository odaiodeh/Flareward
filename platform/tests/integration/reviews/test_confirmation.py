"""Real review capabilities confirm evidence from direct and nested Program reviewers."""

import pytest
from support.review_api import review_api, review_settings
from support.review_programs import review_definition

from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
)
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.identity.domain import Identity
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("nested", [False, True])
async def test_native_confirmation_accepts_only_persisted_review_for_the_called_subtree(
    application, mongo_database, redis_uri, tmp_path, profile, nested
):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    owner = Identity.user("owner")
    settings = review_settings(owner, mongo_database.name, redis_uri)
    settings = settings.model_copy(
        update={
            "application_modules": (*settings.application_modules, "support.review_confirmation")
        }
    )
    resources = (
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.PROVIDER, rid="review"),
            type_key="review_service",
        ),
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="confirm"),
            type_key="confirm_human_review",
            config={"service": "$ref:review"},
        ),
    )
    reviewer = ProgramBody(implementation=review_definition(application.elements, profile))
    if nested:
        reviewer = ProgramBody(
            implementation=GraphDefinition(
                steps=(
                    ProgramCallStep(
                        uid="inner", program=reviewer, inputs=PathBinding(path=("input",))
                    ),
                ),
                entry="inner",
                exit="inner",
                outputs=PathBinding(path=("results", "inner")),
            )
        )
    implementation = CustomCoordinatorDefinition(
        implementation="fixture_review_confirmation",
        version="1",
        config={
            "confirmation": ElementBundleResolver(application.elements)
            .resolve(resources[1].key, resources)
            .model_dump(mode="json"),
            "execution": {"profile": profile},
        },
        children={"reviewer": reviewer},
    )
    subject = {"candidate": "exact-immutable-work"}
    async with review_api(
        owner, mongo_database.name, redis_uri, tmp_path, settings=settings
    ) as api:
        revision = await api.publish("confirmed-review", implementation)
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": api.root,
                "program": revision.reference.model_dump(mode="json"),
                "inputs": subject,
            },
        )
        assert started.status_code == 202, started.text
        review = await api.pending()
        response = await api.http.post(
            f"/api/reviews/{review.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "approve-exact-work",
                "expected_revision": review.revision,
                "decision": "approve",
                "data": {"feedback": "verified"},
            },
        )
        assert response.status_code == 200, response.text
        result = await api.http.get(f"/api/executions/{api.root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
        record = result.json()["result"]
        assert (
            record["review_id"] == review.review_id and record["response"]["decision"] == "approve"
        )
        assert record["specification"]["subject"] == subject
        children = await api.http.get(f"/api/executions/{api.root}/children", headers=api.human)
        assert children.status_code == 200, children.text
        # The caller's selected reviewer may itself have delegated to a graph child.
        child_id = children.json()[0]["execution_id"]
        assert (child_id != record["execution_id"]) == nested
        for change in (
            {"within_execution_id": "sibling"},
            {"policy": "different@1"},
            {"subject": {"candidate": "changed"}},
        ):
            refused = await api.http.post(
                "/api/reviews/confirmations",
                headers=api.human,
                json={
                    "review_id": review.review_id,
                    "within_execution_id": child_id,
                    "policy": "release@1",
                    "subject": subject,
                    **change,
                },
            )
            assert refused.status_code == 409, refused.text
