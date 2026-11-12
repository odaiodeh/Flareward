"""Replaceable review Programs cannot replace persisted acceptance authority."""

import asyncio

import pytest
from pydantic import ValidationError
from support.design_runtime import DesignRuntime
from support.feature_design import design_definition
from support.operations import operation_bundle

from lumora.services.reviews.ports import ReviewConflict
from plugins.adlc.programs.design import FeatureDesignConfig, feature_design
from plugins.adlc.programs.reviewer import ReviewDependency
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS


@pytest.fixture
def review_case(application):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    config = FeatureDesignConfig.model_validate(design_definition(application.elements).config)
    return config, {"task": "implement", "acceptance_criteria": ["verified"]}


async def test_returned_approval_cannot_replace_persisted_rejection(review_case):
    config, inputs = review_case
    runtime = DesignRuntime(["reject"])
    start = runtime.start_child

    async def forged(name, value, *, key, environment_imports=None):
        child = await start(name, value, key=key)
        if name == "reviewer":
            original = child.result

            async def result():
                returned = await original()
                returned["review"]["response"]["decision"] = "approve"
                return returned

            child.result = result
        return child

    runtime.start_child = forged
    result = await feature_design(runtime, inputs, config.model_copy(update={"max_revisions": 0}))
    assert result["outcome"] == "revisions_exhausted"
    assert result["review"]["review"]["response"]["decision"] == "reject"


async def test_previous_review_cannot_substitute_for_current_reviewer_occurrence(review_case):
    config, inputs = review_case
    runtime = DesignRuntime(["reject", "approve"])
    start = runtime.start_child
    results = []

    async def stale(name, value, *, key, environment_imports=None):
        child = await start(name, value, key=key)
        if name == "reviewer":
            original = child.result

            async def result():
                returned = await original()
                results.append(returned)
                return results[0]

            child.result = result
        return child

    runtime.start_child = stale
    with pytest.raises(ReviewConflict):
        await feature_design(runtime, inputs, config)
    assert len(results) == 2


async def test_cancelling_caller_cancels_active_reviewer(review_case):
    config, inputs = review_case
    runtime = DesignRuntime([])

    async def cancelled(name, *, timeout=None):
        raise asyncio.CancelledError()

    runtime.receive = cancelled
    with pytest.raises(asyncio.CancelledError):
        await feature_design(runtime, inputs, config)
    assert len(runtime.review_children.children) == 1
    assert runtime.review_children.children[0].cancelled
    assert len(runtime.work) == 1


def test_reviewer_cannot_overwrite_designer_dependency(review_case):
    config, _ = review_case
    with pytest.raises(ValidationError, match="distinct Program dependencies"):
        FeatureDesignConfig.model_validate({**config.model_dump(), "designer": "reviewer"})


def test_review_confirmation_requires_registered_authority(review_case, application):
    config, _ = review_case
    with pytest.raises(ValidationError, match="registered scoped service"):
        ReviewDependency.model_validate(
            {
                **config.review.model_dump(),
                "confirmation": operation_bundle(application.elements),
            }
        )
