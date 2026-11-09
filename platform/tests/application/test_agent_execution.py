"""Async reasoning and tool execution preserve conversation and cancellation ownership."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import create_autospec

import pytest
from pydantic import BaseModel, ConfigDict

from flareward.elements.agents.config import AgentConfig
from flareward.elements.agents.domain.models import AgentAction, StepType
from flareward.elements.agents.execution import AgentActionExecutor, AgentIterator
from flareward.elements.agents.execution.handlers import AutoExecutionHandler
from flareward.elements.agents.parsers import ToolCallParser
from flareward.elements.agents.strategies import ReActStrategy
from flareward.elements.behaviors.agent_capable import AgentCapableMixin
from flareward.elements.behaviors.llm_capable import LlmCapableMixin
from flareward.elements.behaviors.streaming_capable import StreamingCapableMixin
from flareward.elements.messaging.domain.messages import ChatMessage, Role, ToolCall
from flareward.elements.ports.llm import BaseLLM
from flareward.elements.ports.tool import BaseTool
from flareward.elements.tools.executor import ToolExecutorManager
from flareward.elements.tools.policies import RetryPolicy
from flareward.services.interactions.tools.models import ToolAccessMode
from flareward.services.tracing import NoOpTracingService, ObservationHandle


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentHarness(AgentCapableMixin, LlmCapableMixin, StreamingCapableMixin):
    """Compose production application capabilities without a graph-node adapter."""


class AsyncTool(BaseTool):
    name = "evidence"
    description = "Return deterministic evidence on the caller's event loop."
    args_schema = NoArguments

    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.closed = False

    async def run(self) -> str:
        assert asyncio.get_running_loop() is self.loop
        self.started.set()
        try:
            await self.release.wait()
            return "verified evidence"
        finally:
            self.closed = True


class IterationTracing(NoOpTracingService):
    def __init__(self) -> None:
        self.started: list[int] = []
        self.closed: list[int] = []
        self.tools_closed: list[str] = []

    @contextmanager
    def trace_agent_iteration(
        self, iteration: int, strategy: str = ""
    ) -> Iterator[ObservationHandle]:
        self.started.append(iteration)
        try:
            with super().trace_agent_iteration(iteration, strategy) as handle:
                yield handle
        finally:
            self.closed.append(iteration)

    @contextmanager
    def trace_tool(self, tool_name, tool_input=None):
        try:
            with super().trace_tool(tool_name, tool_input) as handle:
                yield handle
        finally:
            self.tools_closed.append(tool_name)


@pytest.fixture
async def agent_case():
    tool = AsyncTool()
    tracing = IterationTracing()
    manager = ToolExecutorManager(tracing=tracing)
    manager.set_tools({tool.name: tool})

    async def chat(messages, tools):
        assert asyncio.get_running_loop() is tool.loop
        observation = next((m for m in reversed(messages) if m.role == Role.TOOL), None)
        if observation is None:
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Read evidence first.",
                tool_calls=[ToolCall(name=tool.name, args={}, tool_call_id="evidence-call")],
            )
        assert observation.tool_call_id == "evidence-call"
        return ChatMessage(role=Role.ASSISTANT, content=observation.content)

    iterator = AgentIterator(
        strategy=ReActStrategy(
            llm_chat=chat,
            tools=[tool],
            parser=ToolCallParser(),
            min_reasoning_length=1,
        ),
        execution_handler=AutoExecutionHandler(AgentActionExecutor(tool_executor_manager=manager)),
        tracing=tracing,
    )
    return tool, iterator, tracing, manager


async def test_native_agent_awaits_tools_and_counts_reasoning_iterations(agent_case):
    tool, iterator, tracing, _ = agent_case
    task = asyncio.create_task(anext(iterator))
    await asyncio.wait_for(tool.started.wait(), timeout=2)
    assert not task.done()
    tool.release.set()
    first = await task
    rest = [step async for step in iterator]
    assert [step.type for step in (first, *rest)] == [
        StepType.PLANNING,
        StepType.OBSERVATION,
        StepType.PLANNING,
        StepType.FINISH,
    ]
    assert rest[-1].data.output == "verified evidence"
    assert tracing.started == tracing.closed == [1, 2]
    assert tool.closed


async def test_agent_cancellation_closes_tool_and_iteration_trace(agent_case):
    tool, iterator, tracing, _ = agent_case
    task = asyncio.create_task(anext(iterator))
    await asyncio.wait_for(tool.started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert tool.closed
    assert tracing.started == tracing.closed == [1]
    assert tracing.tools_closed == [tool.name]


async def test_missing_tools_do_not_reorder_batch_observations(agent_case):
    tool, _, _, manager = agent_case
    tool.release.set()
    actions = [
        AgentAction(tool=tool.name, tool_input={}, id="known"),
        AgentAction(tool="missing", tool_input={}, id="unknown"),
    ]
    observations = await AgentActionExecutor(tool_executor_manager=manager).execute_batch(actions)
    assert [observation.action_id for observation in observations] == ["known", "unknown"]
    assert observations[0].success and not observations[1].success


async def test_agent_deadline_interrupts_waiting_tool_and_finishes_cleanup(agent_case):
    tool, iterator, _, _ = agent_case
    agent = AgentHarness(llm=create_autospec(BaseLLM, instance=True))
    result = await asyncio.wait_for(
        agent.run_agent([], iterator.strategy, config=AgentConfig(max_execution_time=0.05)),
        timeout=2,
    )
    assert not result["success"]
    assert result["error"] == "Agent execution timed out"
    assert tool.started.is_set() and tool.closed


@pytest.mark.parametrize("access_mode", [ToolAccessMode.WRITE, ToolAccessMode.DESTRUCTIVE])
async def test_generic_retry_does_not_repeat_effectful_tools(agent_case, access_mode):
    tool, _, _, _ = agent_case
    tool.access_mode = access_mode
    error = RuntimeError("Unknown acceptance of an effect")
    policy = RetryPolicy(max_retries=1, initial_delay=0, jitter=False)
    with pytest.raises(RuntimeError) as failure:
        await policy.handle_error(error, tool, {})
    assert failure.value is error
    assert not tool.started.is_set()


async def test_read_retry_awaits_the_native_tool_contract(agent_case):
    tool, _, _, _ = agent_case
    tool.release.set()
    policy = RetryPolicy(max_retries=1, initial_delay=0, jitter=False)
    assert await policy.handle_error(RuntimeError("Read failed"), tool, {}) == "verified evidence"
    assert tool.started.is_set() and tool.closed
