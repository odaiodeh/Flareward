"""Capabilities cache belongs to one composed reader, including concurrent and mutable callers."""

import asyncio
from unittest.mock import create_autospec

from lumora.services.actions.contracts import ActionSettings
from plugins.actions.llms.openai.capabilities import ModelCapabilities


async def test_capabilities_readers_do_not_share_cached_configuration_and_return_detached_data():
    first, second = (
        create_autospec(ActionSettings, instance=True, spec_set=True) for _ in range(2)
    )
    first.get_section.return_value = {"capabilities": {"first": {"reasoning": ["low"]}}}
    second.get_section.return_value = {"capabilities": {"second": {"reasoning": ["minimal"]}}}
    cached = ModelCapabilities(first)
    values = await asyncio.gather(*(cached.load() for _ in range(10)))
    first.get_section.assert_awaited_once_with("openai_model_capabilities")
    values[0]["first"]["reasoning"].clear()
    assert (await cached.load())["first"]["reasoning"] == ["low"]
    assert set(await ModelCapabilities(second).load()) == {"second"}
    refreshing = ModelCapabilities(first, ttl=0)
    assert "first" in await refreshing.load()
    first.get_section.return_value = {"capabilities": {"updated": {}}}
    assert set(await refreshing.load()) == {"updated"}
