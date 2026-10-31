"""Claude Agent Node - Runs autonomous Claude Agent SDK sessions.

Delegates work to a Claude Agent SDK session configured with
model, tools, skills, and authentication credentials.

Tool-call permissions are managed by the HITL system (via a
``PreToolUse`` hook) instead of the SDK's built-in permission
mode — the SDK always runs with ``bypassPermissions``.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from typing import Any, ClassVar

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    SdkMcpTool,
    ServerToolUseBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
)

from mas.application.agents.approvals import HITLToolGatekeeper
from mas.application.capabilities.hitl_capable import HITLCapableMixin
from mas.application.capabilities.iem_capable import IEMCapableMixin
from mas.application.capabilities.retriever_capable import RetrieverCapableMixin
from mas.application.capabilities.workload_capable import WorkloadCapableMixin
from mas.application.elements.node import BaseNode
from mas.application.ports.tool import BaseTool
from mas.application.ports.tool_provider import ToolProvider
from mas.core.async_work import await_owned
from mas.core.hitl.models import HITLMode, RequestOrigin
from mas.domain.messages import ChatMessage, Role
from mas.domain.workloads import AgentResult, Task
from mas.elements.nodes.claude_agent.identifiers import EffortLevel
from mas.elements.tools.common.claude_sdk_converter import ClaudeSDKConverter
from mas.graph.state.state_view import StateView

from .hitl_hook import CLAUDE_BUILTIN_ACCESS_MODES, HITLHook

logger = logging.getLogger(__name__)


class ClaudeAgentNode(
    WorkloadCapableMixin,
    IEMCapableMixin,
    RetrieverCapableMixin,
    HITLCapableMixin,
    BaseNode,
):
    """Claude Agent Node - Runs Claude Agent SDK sessions autonomously.

    Architecture:
    - Builds ClaudeAgentOptions from stored configuration
    - Constructs environment with auth credentials (Vertex AI)
    - Prepares working directory (optionally cloning skills repos)
    - Calls query() with the task content as prompt
    - Streams AssistantMessage text blocks as llm_token events
    - Converts ResultMessage to AgentResult
    - Routes response via IEM (same pattern as A2A node)

    HITL integration:
    - When HITL is active, a ``PreToolUse`` hook is attached to
      ``ClaudeAgentOptions.hooks`` that gates every tool call through
      the shared ``HITLToolGatekeeper``.
    """

    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
        self,
        *,
        # Auth (Vertex AI)
        vertex_project_id: str = "",
        vertex_region: str = "us-east5",
        # Model
        model: str = "claude-sonnet-4-6",
        effort: EffortLevel = EffortLevel.MEDIUM,
        # Agent behavior
        system_prompt: str = "",
        max_turns: int | None = 200,
        # Skills
        skills_repos: dict[str, str] | None = None,
        cwd: str | None = None,
        # Advanced
        env_vars: dict[str, str] | None = None,
        # Integration
        tools: list[BaseTool] | None = None,
        mcp_providers: list[ToolProvider] | None = None,
        # Runtime context
        shared_storage: str = "/app/shared",
        # HITL + execution context (forwarded to HITLCapableMixin)
        hitl_mode: HITLMode = HITLMode.SKIP,
        execution_holder: Any = None,
        # Standard
        retriever: Any = None,
        **kwargs: Any,
    ):
        super().__init__(
            retriever=retriever,
            hitl_mode=hitl_mode,
            execution_holder=execution_holder,
            **kwargs,
        )

        self._vertex_project_id = vertex_project_id
        self._vertex_region = vertex_region
        self._model = model
        self._effort = effort
        self._system_prompt = system_prompt
        self._max_turns = max_turns
        self._skills_repos = skills_repos or {}
        self._cwd = cwd
        self._env_vars = env_vars or {}
        self._domain_tools: list[BaseTool] = tools or []
        self._mcp_providers = mcp_providers or []
        self._shared_storage = shared_storage

        self._max_context_messages = 20

    async def run(self, state: StateView) -> StateView:
        """Main entry point - process all incoming TaskPackets."""

        await self.process_packets(state)
        return state

    # ========== TASK PROCESSING ==========

    async def handle_task_packet(self, packet) -> None:
        """Process task by running a Claude Agent SDK session."""
        task = None
        try:
            task = packet.extract_task()
            task.mark_processed(self.uid)

            if task.thread_id:
                self.workspaces.add_task(task.thread_id, task)

            prompt = await self._build_prompt(task)

            response_text, execution_metadata = await self._execute_claude_session(prompt)

            agent_result = self._create_agent_result(response_text, execution_metadata)

            if task.thread_id:
                self.workspaces.add_result(task.thread_id, agent_result)

            self._route_response(task, agent_result, packet)

            duration_s = (execution_metadata.get("duration_ms") or 0) / 1000
            logger.info(
                "claude.session_completed",
                extra={
                    "node_uid": self.uid,
                    "turns": execution_metadata.get("num_turns"),
                    "cost_usd": execution_metadata.get("total_cost_usd", 0),
                    "input_tokens": execution_metadata.get("input_tokens", 0),
                    "output_tokens": execution_metadata.get("output_tokens", 0),
                    "duration_s": round(duration_s, 1),
                },
            )

        except Exception as e:
            logger.error("ClaudeAgent %s: Error processing task: %s", self.uid, e)
            error_result = AgentResult(
                content=f"Error running Claude Agent SDK: {str(e)}",
                agent_id=self.uid,
                agent_name=self.display_name,
                success=False,
                error=str(e),
            )
            if task and task.thread_id:
                self.workspaces.add_result(task.thread_id, error_result)
            if task:
                self._route_response(task, error_result, packet)

    # ========== CONTEXT BUILDING ==========

    async def _build_prompt(self, task: Task) -> str:
        """Build prompt from task content, workspace history, and retriever."""
        context_parts = []

        if task.thread_id:
            workspace_messages = self.workspaces.get_recent_messages(
                task.thread_id, self._max_context_messages
            )
            history = deepcopy(workspace_messages)

            if (
                history
                and hasattr(history[-1], "role")
                and history[-1].role == Role.USER
                and history[-1].content == task.content
            ):
                history.pop()

            if history:
                context_parts.append(self._format_conversation_history(history))

            agent_results_msg = self._build_agent_results_context(task.thread_id)
            if agent_results_msg:
                context_parts.append(agent_results_msg.content)

        user_msg = ChatMessage(role=Role.USER, content=task.content)
        if self.retriever:
            user_msg = await self.augment_with_context(user_msg)
        context_parts.append(user_msg.content)

        return "\n\n".join(context_parts)

    def _format_conversation_history(self, messages: list[ChatMessage]) -> str:
        parts = ["CONVERSATION CONTEXT:"]
        for msg in messages:
            role_label = msg.role.value.upper()
            parts.append(f"[{role_label}]: {msg.content}")
        return "\n".join(parts)

    def _build_agent_results_context(self, thread_id: str) -> ChatMessage | None:
        if not thread_id:
            return None

        workspace_results = self.workspaces.get_results(thread_id)
        if not workspace_results:
            return None

        results_text = "PREVIOUS AGENT RESULTS:\n"
        for i, result in enumerate(workspace_results, 1):
            results_text += f"{i}. {result.agent_name}: {result.content}\n"

        return ChatMessage(role=Role.USER, content=results_text)

    # ========== CLAUDE SDK EXECUTION ==========

    async def _execute_claude_session(self, prompt: str) -> tuple[str, dict[str, Any]]:
        """Execute Claude Agent SDK session synchronously.

        Uses AsyncBridge to run the async query() generator.
        Streams text blocks as llm_token events if streaming is active.
        """
        options = await self._build_options()
        return await self._async_execute(prompt, options)

    async def _async_execute(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> tuple[str, dict[str, Any]]:
        """Async execution of Claude Agent SDK query."""
        accumulated_text = ""
        execution_metadata: dict[str, Any] = {}
        emitted_tool_call_ids: set[str] = set()
        tool_id_to_name: dict[str, str] = {}

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        accumulated_text += block.text
                        if self.is_streaming():
                            self._stream(
                                {
                                    "type": "llm_token",
                                    "chunk": block.text,
                                }
                            )

                    elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                        tool_id_to_name[block.id] = block.name
                        if block.id not in emitted_tool_call_ids:
                            emitted_tool_call_ids.add(block.id)
                            if self.is_streaming():
                                self._stream(
                                    {
                                        "type": "tool_calling",
                                        "tool": block.name,
                                        "call_id": block.id,
                                        "args": block.input,
                                    }
                                )

            elif isinstance(message, UserMessage):
                if isinstance(message.content, list):
                    for block in message.content:
                        if isinstance(block, ToolResultBlock):
                            if self.is_streaming():
                                self._stream(
                                    {
                                        "type": "tool_result",
                                        "tool": tool_id_to_name.get(block.tool_use_id, "unknown"),
                                        "call_id": block.tool_use_id,
                                        "output": self._extract_tool_result_text(block.content),
                                    }
                                )

            elif isinstance(message, ResultMessage):
                execution_metadata = {
                    "session_id": getattr(message, "session_id", None),
                    "duration_ms": getattr(message, "duration_ms", None),
                    "duration_api_ms": getattr(message, "duration_api_ms", None),
                    "is_error": getattr(message, "is_error", False),
                    "num_turns": getattr(message, "num_turns", None),
                    "stop_reason": getattr(message, "stop_reason", None),
                    "total_cost_usd": getattr(message, "total_cost_usd", None),
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
                usage = getattr(message, "usage", None)
                if usage and isinstance(usage, dict):
                    execution_metadata["input_tokens"] = usage.get("input_tokens", 0)
                    execution_metadata["output_tokens"] = usage.get("output_tokens", 0)

                result_text = getattr(message, "result", None)
                if result_text:
                    accumulated_text = result_text

        return accumulated_text, execution_metadata

    @staticmethod
    def _extract_tool_result_text(
        content: str | list[dict[str, Any]] | dict[str, Any] | None,
    ) -> str:
        """Extract displayable text from tool result content, truncated to 500 chars."""
        max_len = 500
        if content is None:
            return ""
        if isinstance(content, str):
            return content[:max_len]
        if isinstance(content, dict):
            text = str(content)
            return text[:max_len]
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            text = "\n".join(parts) if parts else str(content)
            return text[:max_len]
        return str(content)[:max_len]

    async def _collect_tools(self) -> list[BaseTool]:
        """Collect configured tools in this invocation's execution environment."""
        tools = list(self._domain_tools)
        for provider in self._mcp_providers:
            tools.extend(await provider.get_tools())
        return tools

    async def _build_options(self) -> ClaudeAgentOptions:
        """Build SDK options for the current invocation environment."""
        env = self._build_env()
        work_dir = await await_owned(asyncio.to_thread(self._prepare_working_directory))

        kwargs: dict[str, Any] = {
            "model": self._model,
            "permission_mode": "bypassPermissions",
            "effort": self._effort.value,
            "max_turns": self._max_turns,
            "cwd": work_dir,
            "env": env,
        }

        if self._system_prompt:
            kwargs["system_prompt"] = self._system_prompt

        sdk_tools = await self._collect_sdk_tools()
        if sdk_tools:
            kwargs.setdefault("mcp_servers", {})["mas-tools"] = create_sdk_mcp_server(
                "mas-tools", tools=sdk_tools
            )

        hitl_hook = await self._build_hitl_hook()
        if hitl_hook is not None:
            kwargs["hooks"] = {"PreToolUse": [hitl_hook]}
            logger.info(
                "ClaudeAgent %s: PreToolUse HITL hook attached",
                self.uid,
            )
        else:
            logger.info(
                "ClaudeAgent %s: HITL hook NOT attached (hitl_mode=%s, gate=%s, policy=%s)",
                self.uid,
                self._hitl_mode.value,
                self._approval_gate is not None,
                self._approval_policy is not None,
            )

        return ClaudeAgentOptions(**kwargs)

    # ========== HITL HOOK ==========

    async def _build_hitl_hook(self) -> HookMatcher | None:
        """Build a ``PreToolUse`` HookMatcher if HITL is active."""
        if not self._should_activate_hitl():
            return None

        origin = RequestOrigin(
            node_uid=self.uid,
            node_display_name=self.display_name,
            session_id=self.hitl_session_id,
        )

        tool_registry: dict[str, BaseTool] = {t.name: t for t in self._domain_tools}
        for provider in self._mcp_providers:
            for tool in await provider.get_tools():
                tool_registry[tool.name] = tool

        gatekeeper = HITLToolGatekeeper(
            gate=self._approval_gate,
            policy=self._approval_policy,
            tool_registry=tool_registry,
            origin=origin,
            builtin_access_modes=CLAUDE_BUILTIN_ACCESS_MODES,
        )

        logger.info(
            "ClaudeAgent %s: HITL hook enabled (hitl_mode=%s) with %d registered tools",
            self.uid,
            self._hitl_mode.value,
            len(tool_registry),
        )

        return HookMatcher(hooks=[HITLHook(gatekeeper)])

    # ========== SDK TOOLS ==========

    async def _collect_sdk_tools(self) -> list[SdkMcpTool]:
        """Collect domain + MCP tools and convert to Claude SDK format."""
        collected = await self._collect_tools()
        return ClaudeSDKConverter.to_sdk(collected)

    # ========== ENVIRONMENT ==========

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for Vertex AI SDK authentication."""
        env = dict(self._env_vars)

        env["CLAUDE_CODE_USE_VERTEX"] = "1"
        env["ANTHROPIC_VERTEX_PROJECT_ID"] = self._vertex_project_id
        env["CLOUD_ML_REGION"] = self._vertex_region

        return env

    def _prepare_working_directory(self) -> str:
        """Prepare working directory for the Claude agent session."""
        if self._cwd:
            work_dir = self._cwd
        elif self.hitl_session_id:
            work_dir = os.path.join(self._shared_storage, self.hitl_session_id, self.uid)
        else:
            work_dir = tempfile.mkdtemp(prefix="claude_agent_")

        os.makedirs(work_dir, exist_ok=True)

        if self._skills_repos:
            self._clone_skills_repos(work_dir)

        return work_dir

    def _clone_skills_repos(self, base_dir: str) -> None:
        """Install skills into .claude/skills/ within the working directory."""
        skills_dir = os.path.join(base_dir, ".claude", "skills")
        os.makedirs(skills_dir, exist_ok=True)

        for skill_path, repo_url in self._skills_repos.items():
            skill_name = os.path.basename(skill_path.rstrip(os.sep))
            if os.path.isdir(os.path.join(skills_dir, skill_name)):
                continue
            try:
                self._install_skill(repo_url, skill_path, skills_dir)
            except Exception as e:
                logger.error(
                    "ClaudeAgent %s: Failed to install skill from %s (path: %s): %s",
                    self.uid,
                    repo_url,
                    skill_path,
                    e,
                )

    def _install_skill(self, repo_url: str, skill_path: str, skills_dir: str) -> None:
        """Clone a repo to temp, copy only the skill subfolder to skills_dir."""
        tmp_dir = tempfile.mkdtemp(prefix="claude_skill_clone_")
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", repo_url, tmp_dir],
                check=True,
                capture_output=True,
                timeout=120,
            )

            source_path = os.path.join(tmp_dir, skill_path)
            if not os.path.isdir(source_path):
                raise FileNotFoundError(f"Skill path '{skill_path}' not found in repo {repo_url}")

            skill_name = os.path.basename(source_path.rstrip(os.sep))
            target_dir = os.path.join(skills_dir, skill_name)

            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(source_path, target_dir)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ========== RESULT HANDLING ==========

    def _create_agent_result(
        self,
        response_text: str,
        metadata: dict[str, Any],
    ) -> AgentResult:
        is_error = metadata.get("is_error", False)

        return AgentResult(
            content=response_text,
            agent_id=self.uid,
            agent_name=self.display_name,
            success=not is_error,
            error=metadata.get("stop_reason") if is_error else None,
            reasoning="",
            execution_metadata={
                "claude_agent_sdk": True,
                "model": self._model,
                "effort": self._effort.value,
                "session_id": metadata.get("session_id"),
                "num_turns": metadata.get("num_turns"),
                "total_cost_usd": metadata.get("total_cost_usd"),
                "duration_ms": metadata.get("duration_ms"),
                "stop_reason": metadata.get("stop_reason"),
                "streaming": self.is_streaming(),
            },
            metrics={
                "input_tokens": metadata.get("input_tokens", 0),
                "output_tokens": metadata.get("output_tokens", 0),
                "total_cost_usd": metadata.get("total_cost_usd", 0),
            },
        )

    # ========== RESPONSE ROUTING ==========

    def _route_response(
        self,
        task: Task,
        agent_result: AgentResult,
        original_packet,
    ) -> None:
        """Route response based on task.should_respond."""
        if not task.should_respond:
            self._execute_normal_broadcast(task, agent_result)
        else:
            adjacent_nodes_uids = self._get_adjacent_nodes_uids()
            if task.response_to and task.response_to in adjacent_nodes_uids:
                self._execute_direct_response(task, agent_result, original_packet)
            else:
                self._execute_broadcast_with_response(task, agent_result)

    def _get_adjacent_nodes_uids(self) -> set[str]:
        adjacent_nodes = self.get_adjacent_nodes()
        return set(adjacent_nodes.keys())

    def _execute_direct_response(
        self,
        task: Task,
        agent_result: AgentResult,
        original_packet,
    ) -> None:
        response_task = Task.respond_success(
            original_task=task,
            result=agent_result,
            processed_by=self.uid,
        )
        self.reply_task(original_packet, response_task)

    def _execute_broadcast_with_response(
        self,
        task: Task,
        agent_result: AgentResult,
    ) -> None:
        response_task = task.fork(
            content="finished work",
            processed_by=self.uid,
            result=agent_result,
        )
        response_task.should_respond = True
        response_task.response_to = task.response_to
        response_task.correlation_task_id = task.task_id
        self.broadcast_task(response_task)

    def _execute_normal_broadcast(
        self,
        task: Task,
        agent_result: AgentResult,
    ) -> None:
        forked_task = task.fork(
            content="continue work",
            processed_by=self.uid,
            result=agent_result,
        )
        self.broadcast_task(forked_task)
