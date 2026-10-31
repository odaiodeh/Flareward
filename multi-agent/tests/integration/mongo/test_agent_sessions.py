"""Actual agents and typed transitive tools retain state through native program sessions."""

from uuid import uuid4

import pytest
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from support.agent_session import ELEMENT_SPECIFICATIONS
from support.agent_session_assertions import assert_agent_turn
from support.agent_session_http import create_agent_session, execute_agent_turn
from support.blueprint_http import library_api


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("chat", [False, True])
async def test_saved_agent_blueprint_runs_two_turns_with_shared_transitive_resources(
    secret_settings, profile, chat
):
    elements = ElementRegistry()
    for specification in ELEMENT_SPECIFICATIONS:
        elements.register_spec_class(specification)
    seed = uuid4().hex
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner"), elements=elements) as http:
        session_id, definition = await create_agent_session(http, seed, profile=profile, chat=chat)
        assert len(definition["implementation"]["resources"]) == 9
        previous_review = None
        for turn in (1, 2):
            execution_id = uuid4().hex
            _, session = await execute_agent_turn(
                http, session_id, execution_id, f"Research request {turn}", chat=chat
            )
            previous_review = assert_agent_turn(session, seed, execution_id, turn, previous_review)
            if turn == 1:
                leaf = next(
                    item
                    for item in definition["implementation"]["resources"]
                    if item["name"] == "Evidence data"
                )
                edited = await http.put(
                    "/api/resources/" + leaf["key"]["rid"],
                    json={"config": {"value": "changed after publication"}, "expected_version": 1},
                )
                assert edited.status_code == 200, edited.text
