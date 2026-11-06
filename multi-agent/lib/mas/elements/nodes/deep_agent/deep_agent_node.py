"""
Deep Agent Node — delegates execution to a LangChain Deep Agent graph.

Follows the same architectural pattern as ``CustomAgentNode`` and ``A2AAgentNode``:
  - Receives work via IEM ``TaskPacket``s
  - Builds conversation context from workspace history
  - Processes through an execution engine (here: Deep Agent graph)
  - Routes results back via IEM broadcast / reply

The Deep Agent graph is compiled lazily on first ``run()`` because MCP tools
require network initialization that isn't available at ``__init__`` time.
"""

import asyncio
import logging
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import BackendProtocol
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool as LangChainBaseTool

from mas.application.capabilities.hitl_capable import HITLCapableMixin
from mas.application.capabilities.retriever_capable import RetrieverCapableMixin
from mas.application.elements.node import BaseNode
from mas.application.ports.llm import BaseLLM
from mas.application.ports.tool import BaseTool
from mas.application.ports.tool_provider import ToolProvider
from mas.core.async_work import await_owned
from mas.core.hitl.models import HITLMode, RequestOrigin
from mas.domain.messages import ChatMessage, Role
from mas.domain.workloads import AgentResult, Task
from mas.elements.llms.common.chat.converter import LangChainConverter, normalise_content
from mas.elements.llms.common.langchain_adapter import BaseLLMChatModelAdapter
from mas.elements.nodes.deep_agent.hitl_middleware import HITLMiddleware
from mas.elements.tools.common.converter import LangChainToolsConverter
from mas.graph.capabilities.messaging import GraphMessagingMixin
from mas.graph.capabilities.workloads import GraphWorkloadMixin

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Value objects
# ------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable result from a Deep Agent invocation."""

    output: str = ""
    success: bool = True
    error: str | None = None
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Node
# ------------------------------------------------------------------


class DeepAgentNode(
    GraphWorkloadMixin,
    GraphMessagingMixin,
    RetrieverCapableMixin,
    HITLCapableMixin,
    BaseNode,
):
    """Agent node that delegates to a LangChain Deep Agent for execution.

    Architecture:
    - Wraps a LangChain Deep Agent graph (``create_deep_agent``)
    - Lazily compiles the graph on first ``run()`` (MCP tools need network init)
    - Uses ``LocalBackend`` for session-scoped filesystem access
    - Bridges domain ``BaseTool`` → LangChain tools via ``LangChainToolsConverter``
    - Supports streaming: forwards ``llm_token`` and ``tool_calling`` events
    - Same routing logic as CustomAgent / A2AAgent (``should_respond``)
    """

    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
        self,
        *,
        llm: BaseLLM,
        tools: list[BaseTool] | None = None,
        mcp_providers: list[ToolProvider] | None = None,
        system_message: str = "",
        retriever: Any = None,
        cwd: str | None = None,
        env_vars: dict[str, str] | None = None,
        execution_holder=None,
        shared_storage: str = "/app/shared",
        hitl_mode: HITLMode = HITLMode.SKIP,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            retriever=retriever,
            hitl_mode=hitl_mode,
            execution_holder=execution_holder,
            **kwargs,
        )

        self._llm = llm
        self._domain_tools: list[BaseTool] = tools or []
        self._mcp_providers: list[ToolProvider] = mcp_providers or []
        self._system_message = system_message
        self._cwd = cwd
        self._env_vars: dict[str, str] = env_vars or {}
        self._shared_storage = shared_storage

        self._compiled_agent: Any = None

    # ==================================================================
    # Graph lifecycle
    # ==================================================================

    async def run(self, state: Any) -> Any:
        """Main entry point — build the Deep Agent (if needed), then process packets."""

        await self._ensure_compiled()
        await self.process_packets()
        return state

    async def _ensure_compiled(self) -> None:
        """Lazily compile the Deep Agent graph on first execution."""
        if self._compiled_agent is not None:
            return

        langchain_tools = await self._collect_langchain_tools()
        self._compiled_agent = await self._build_deep_agent(langchain_tools)
        logger.info("DeepAgent %s: compiled graph with %d tools", self.uid, len(langchain_tools))

    async def _collect_langchain_tools(self) -> list[LangChainBaseTool]:
        """Collect configured tools in this invocation's execution environment."""
        tools = list(self._domain_tools)
        for provider in self._mcp_providers:
            tools.extend(await provider.get_tools())
        return LangChainToolsConverter.to_lc(tools)

    async def _build_deep_agent(self, tools: list[LangChainBaseTool]) -> Any:
        """Compile a Deep Agent graph with LocalShellBackend for filesystem access.

        When HITL is active (gate + policy injected), a ``HITLMiddleware``
        is added to the Deep Agent's middleware stack.  The middleware
        intercepts tool calls inside LangGraph's tool node, using the
        same ``ApprovalGate`` / ``ToolApprovalPolicy`` as the native
        ``HITLExecutionHandler``.
        """
        adapter = BaseLLMChatModelAdapter(llm=self._llm)
        backend = await await_owned(asyncio.to_thread(self._build_backend))
        middleware = await self._build_middleware()

        return create_deep_agent(
            model=adapter,
            tools=tools or None,
            system_prompt=self._system_message or None,
            backend=backend,
            middleware=middleware,
        )

    # ==================================================================
    # HITL middleware
    # ==================================================================

    async def _build_middleware(self) -> list:
        """Assemble the middleware stack for Deep Agent compilation."""
        middleware: list = []

        if self._should_activate_hitl():
            origin = RequestOrigin(
                node_uid=self.uid,
                node_display_name=self.display_name,
                session_id=self.hitl_session_id,
            )
            tool_registry = {t.name: t for t in self._domain_tools}
            for provider in self._mcp_providers:
                for tool in await provider.get_tools():
                    tool_registry[tool.name] = tool

            middleware.append(
                HITLMiddleware(
                    gate=self._approval_gate,
                    policy=self._approval_policy,
                    tool_registry=tool_registry,
                    origin=origin,
                )
            )
            logger.info(
                "DeepAgent %s: HITL middleware enabled with %d registered tools",
                self.uid,
                len(tool_registry),
            )

        return middleware

    # ==================================================================
    # Backend / working directory
    # ==================================================================

    def _build_backend(self) -> BackendProtocol:
        """Create the appropriate backend for the Deep Agent.

        LocalShellBackend operates inside the invocation's selected environment.
        """

        root_dir = self._prepare_working_directory()
        env = self._build_env()
        return LocalShellBackend(root_dir=root_dir, virtual_mode=True, env=env)

    def _prepare_working_directory(self) -> str:
        """Derive a session-scoped working directory.

        Priority:
        1. Explicit ``cwd`` override from config
        2. ``{shared_storage}/{session_id}/{node_uid}/`` for session persistence
        3. Temp directory as last resort
        """
        if self._cwd:
            work_dir = self._cwd
        elif self.hitl_session_id:
            work_dir = os.path.join(self._shared_storage, self.hitl_session_id, self.uid)
        else:
            work_dir = tempfile.mkdtemp(prefix="deep_agent_")

        os.makedirs(work_dir, exist_ok=True)
        return work_dir

    def _build_env(self) -> dict[str, str] | None:
        """Build environment variables dict for the backend, or None if empty."""
        if not self._env_vars:
            return None
        return dict(self._env_vars)

    # ==================================================================
    # Task processing (IEM contract)
    # ==================================================================

    async def handle_task_packet(self, packet: Any) -> None:
        """Process a single ``TaskPacket`` through the Deep Agent."""
        task = packet.extract_task()
        task.mark_processed(self.uid)

        try:
            if task.thread_id:
                self.workspaces.add_task(task.thread_id, task)

            conversation_context = self._build_conversation_context(task)
            execution_result = await self._invoke(conversation_context)
            agent_result = self._to_agent_result(execution_result)

            if task.thread_id:
                self.workspaces.add_result(task.thread_id, agent_result)

            self._route_response(task, agent_result, packet)
            logger.info("DeepAgent %s: processed task successfully", self.uid)

        except Exception as exc:
            logger.error("DeepAgent %s: error processing task: %s", self.uid, exc)
            error_result = AgentResult(
                content=f"Error processing task: {exc}",
                agent_id=self.uid,
                agent_name=self.display_name,
                success=False,
                error=str(exc),
            )
            if task.thread_id:
                self.workspaces.add_result(task.thread_id, error_result)
            self._route_response(task, error_result, packet)

    # ==================================================================
    # Context building
    # ==================================================================

    def _build_conversation_context(self, task: Task) -> list[ChatMessage]:
        """Assemble workspace history + agent results + current prompt."""
        context_messages: list[ChatMessage] = []

        if task.thread_id:
            workspace_messages = self.workspaces.get_recent_messages(task.thread_id, 20)
            context_messages.extend(deepcopy(workspace_messages))

        if (
            context_messages
            and context_messages[-1].role == Role.USER
            and context_messages[-1].content == task.content
        ):
            context_messages.pop()

        agent_results_msg = self._build_agent_results_context(task.thread_id)
        if agent_results_msg:
            context_messages.append(agent_results_msg)

        context_messages.append(ChatMessage(role=Role.USER, content=task.content))
        return context_messages

    def _build_agent_results_context(self, thread_id: str | None) -> ChatMessage | None:
        """Summarise previous agent results into a single context message."""
        if not thread_id:
            return None

        results = self.workspaces.get_results(thread_id)
        if not results:
            return None

        lines = [f"{i}. {r.agent_name}: {r.content}" for i, r in enumerate(results, 1)]
        return ChatMessage(
            role=Role.USER,
            content="PREVIOUS AGENT RESULTS:\n" + "\n".join(lines),
        )

    # ==================================================================
    # Deep Agent invocation
    # ==================================================================

    async def _invoke(self, context: list[ChatMessage]) -> ExecutionResult:
        """Route to streaming or synchronous invocation based on channel state."""
        lc_messages = LangChainConverter.to_lc(context)

        if self.is_streaming():
            return await self._invoke_streaming(lc_messages)
        return await self._invoke_completion(lc_messages)

    async def _invoke_completion(self, lc_messages: list[BaseMessage]) -> ExecutionResult:
        """Synchronous (non-streaming) Deep Agent invocation."""
        result = await self._compiled_agent.ainvoke({"messages": lc_messages})

        output_messages = result.get("messages", [])
        last_ai = next(
            (m for m in reversed(output_messages) if isinstance(m, AIMessage)),
            None,
        )

        return ExecutionResult(
            output=normalise_content(last_ai.content) if last_ai else "",
        )

    async def _invoke_streaming(self, lc_messages: list[BaseMessage]) -> ExecutionResult:
        """Stream LLM tokens and tool calls in real time.

        Uses ``stream_mode="messages"`` with ``subgraphs=True`` so that
        events from the general-purpose subagent are also forwarded.
        """
        accumulated_text = ""
        emitted_tool_call_ids: set[str] = set()

        async for chunk in self._compiled_agent.astream(
            {"messages": lc_messages},
            stream_mode="messages",
            subgraphs=True,
            version="v2",
        ):
            if chunk.get("type") != "messages":
                continue

            token, _metadata = chunk["data"]

            if getattr(token, "tool_calls", None) and isinstance(token, AIMessage):
                self._emit_tool_calls(token.tool_calls, emitted_tool_call_ids)
                continue

            if getattr(token, "tool_call_chunks", None):
                continue

            if isinstance(token, AIMessage):
                text = normalise_content(token.content)
                if text:
                    accumulated_text += text
                    self._stream({"type": "llm_token", "chunk": text})

        return ExecutionResult(
            output=accumulated_text,
            metadata={"streaming": True},
        )

    def _emit_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        emitted_ids: set[str],
    ) -> None:
        """Emit ``tool_calling`` events for newly-seen tool calls."""
        for tc in tool_calls:
            call_id = tc.get("id", "")
            if call_id in emitted_ids:
                continue
            emitted_ids.add(call_id)
            self._stream(
                {
                    "type": "tool_calling",
                    "tool": tc.get("name", ""),
                    "call_id": call_id,
                    "args": tc.get("args", {}),
                }
            )

    # ==================================================================
    # Result creation
    # ==================================================================

    def _to_agent_result(self, result: ExecutionResult) -> AgentResult:
        """Translate an ``ExecutionResult`` into a domain ``AgentResult``."""
        content = result.output or result.error or "No output produced"

        return AgentResult(
            content=content,
            agent_id=self.uid,
            agent_name=self.display_name,
            success=result.success,
            error=result.error,
            reasoning=result.reasoning,
            execution_metadata=result.metadata,
            metrics=result.metrics,
        )

    # ==================================================================
    # Response routing (same contract as CustomAgentNode / A2AAgentNode)
    # ==================================================================

    def _route_response(self, task: Task, agent_result: AgentResult, original_packet: Any) -> None:
        """Route the agent result back through IEM based on task directives."""
        if not task.should_respond:
            self._execute_normal_broadcast(task, agent_result)
        else:
            adjacent_uids = self._get_adjacent_node_uids()
            if task.response_to and task.response_to in adjacent_uids:
                self._execute_direct_response(task, agent_result, original_packet)
            else:
                self._execute_broadcast_with_response(task, agent_result)

    def _get_adjacent_node_uids(self) -> set[str]:
        """Get adjacent node UIDs from network topology."""
        return set(self.get_adjacent_nodes().keys())

    def _execute_direct_response(
        self, task: Task, result: AgentResult, original_packet: Any
    ) -> None:
        """Send direct response to requester."""
        response_task = Task.respond_success(
            original_task=task,
            result=result,
            processed_by=self.uid,
        )
        self.reply_task(original_packet, response_task)

    def _execute_broadcast_with_response(self, task: Task, result: AgentResult) -> None:
        """Broadcast with response request — carry original requester info."""
        response_task = task.fork(
            content="finished work",
            processed_by=self.uid,
            result=result,
        )
        response_task.should_respond = True
        response_task.response_to = task.response_to
        response_task.correlation_task_id = task.task_id
        self.broadcast_task(response_task)

    def _execute_normal_broadcast(self, task: Task, result: AgentResult) -> None:
        """Normal broadcast — continue work."""
        forked_task = task.fork(
            content="continue work",
            processed_by=self.uid,
            result=result,
        )
        self.broadcast_task(forked_task)
