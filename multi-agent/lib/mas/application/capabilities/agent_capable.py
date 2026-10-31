"""Agent capability mixin for nodes."""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from mas.application.agents.config import AgentConfig
from mas.application.agents.constants import ErrorMessages, StrategyType
from mas.application.agents.execution import (
    AgentActionExecutor,
    AgentIterator,
    ExecutionHandlerFactory,
)
from mas.application.agents.parsers import OutputParser, ToolCallParser
from mas.application.agents.strategies import AgentStrategy, ReActStrategy
from mas.application.agents.strategies.plan_execute import PlanAndExecuteStrategy
from mas.application.ports.tool import BaseTool
from mas.application.tools.config import ExecutorConfig
from mas.application.tools.executor import ToolExecutorManager
from mas.core.contracts import SupportsStreaming
from mas.domain.agents import AgentAction, AgentStep, StepType
from mas.domain.messages import ChatMessage


class AgentCapableMixin[T: SupportsStreaming]:
    """Self-contained agent capability mixin with direct tool management."""

    def __init_subclass__(cls) -> None:
        """Verify that required capabilities are present."""
        required_attrs = ["chat", "_stream", "is_streaming"]
        missing = []

        for attr in required_attrs:
            if not any(hasattr(base, attr) for base in cls.__mro__):
                missing.append(attr)

        if missing:
            capabilities_map = {
                "chat": "LlmCapableMixin",
                "_stream": "BaseNode",
                "is_streaming": "BaseNode",
            }
            missing_mixins = {capabilities_map[attr] for attr in missing}
            raise TypeError(
                f"{cls.__name__} requires {', '.join(missing_mixins)} to provide: {missing}"
            )

        super().__init_subclass__()

    def __init__(self, **kwargs):
        """Initialize agent capability."""
        super().__init__(**kwargs)
        self._tool_executor_manager: ToolExecutorManager | None = None
        self._default_executor_config: ExecutorConfig | None = None
        self._custom_pre_hooks: list[Callable] = []
        self._custom_post_hooks: list[Callable] = []

    # -------------------------------------------------------------------------
    # Hook Management API
    # -------------------------------------------------------------------------

    def add_pre_execution_hook(self, hook: Callable) -> None:
        """Add a custom pre-execution hook."""
        self._custom_pre_hooks.append(hook)
        # If executor already exists, add to it immediately
        if self._tool_executor_manager:
            self._tool_executor_manager.add_pre_execution_hook(hook)

    def add_post_execution_hook(self, hook: Callable) -> None:
        """Add a custom post-execution hook."""
        self._custom_post_hooks.append(hook)
        # If executor already exists, add to it immediately
        if self._tool_executor_manager:
            self._tool_executor_manager.add_post_execution_hook(hook)

    def set_default_executor_config(self, config: ExecutorConfig) -> None:
        """Set default configuration for ToolExecutorManager."""
        self._default_executor_config = config

    # -------------------------------------------------------------------------
    # Streaming hooks
    # -------------------------------------------------------------------------

    def _ensure_executor(
        self, tools: list[BaseTool], config: ExecutorConfig | None = None
    ) -> ToolExecutorManager:
        """Ensure ToolExecutorManager exists with current tools and config."""
        # Use provided config or default
        executor_config = config or self._default_executor_config or ExecutorConfig.create_default()

        # Create new executor (could optimize to reuse if config unchanged)
        self._tool_executor_manager = ToolExecutorManager(
            **executor_config.to_dict(), tracing=getattr(self, "_tracing", None)
        )
        self._tool_executor_manager.set_tools({tool.name: tool for tool in tools})

        self._setup_standard_hooks()

        # Add custom hooks
        for hook in self._custom_pre_hooks:
            self._tool_executor_manager.add_pre_execution_hook(hook)
        for hook in self._custom_post_hooks:
            self._tool_executor_manager.add_post_execution_hook(hook)

        return self._tool_executor_manager

    def _setup_standard_hooks(self: T) -> None:
        """Setup standard pre/post execution hooks for streaming."""
        if not self._tool_executor_manager:
            return

        # Standard pre-execution hook
        async def standard_pre_hook(tool, args, context):
            tool_call_id = (
                context.get("tool_call_id", f"call_{tool.name}_{id(args)}")
                if context
                else f"call_{tool.name}_{id(args)}"
            )
            if self.is_streaming():
                self._stream(
                    {
                        "type": "tool_calling",
                        "tool": tool.name,
                        "call_id": tool_call_id,
                        "args": args,
                    }
                )

        # Add standard hooks
        self._tool_executor_manager.add_pre_execution_hook(standard_pre_hook)

    def create_strategy(
        self,
        tools: list[BaseTool],
        strategy_type: str = StrategyType.REACT.value,
        *,
        parser: OutputParser | None = None,
        system_message: str | None = None,
        **kwargs,
    ) -> AgentStrategy:
        """Factory method for creating agent strategies."""
        if parser is None:
            parser = ToolCallParser()

        # Create llm_chat callable that binds self.chat
        async def llm_chat(
            messages: list[ChatMessage], tools_subset: list[BaseTool]
        ) -> ChatMessage:
            return await self.chat(messages, tools_subset)

        if strategy_type == StrategyType.REACT.value:
            return ReActStrategy(
                llm_chat=llm_chat,
                tools=tools,
                parser=parser,
                system_message=system_message,
                **kwargs,
            )
        elif strategy_type == StrategyType.PLAN_AND_EXECUTE.value:
            return PlanAndExecuteStrategy(
                llm_chat=llm_chat,
                tools=tools,
                parser=parser,
                system_message=system_message,
                **kwargs,
            )
        # Add more strategies here as needed

        available_types = [e.value for e in StrategyType]
        raise ValueError(
            ErrorMessages.UNKNOWN_STRATEGY_TYPE.format(available_types=", ".join(available_types))
        )

    def create_iterator(
        self,
        messages: list[ChatMessage],
        strategy: AgentStrategy,
        *,
        config: AgentConfig | None = None,
        on_action: Callable[[AgentAction], bool] | None = None,
    ) -> AgentIterator:
        """Create iterator for step-by-step agent execution."""
        if config is None:
            config = AgentConfig()

        # Get tools from strategy
        tools = list(strategy.all_tools.values())

        # Ensure executor exists with strategy's tools and config
        executor_manager = self._ensure_executor(tools, config.executor_config)

        # Create action executor
        action_executor = AgentActionExecutor(
            tool_executor_manager=executor_manager, validate_args=True
        )

        # Create execution handler based on mode (Strategy pattern)
        execution_handler = ExecutionHandlerFactory.create(
            mode=config.execution_mode,
            action_executor=action_executor,
            hitl_config=config.hitl_config,
        )

        tracing = getattr(self, "_tracing", None)

        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler,
            on_action=on_action,
            tracing=tracing,
        )

        # Set initial messages
        iterator.messages = list(messages)

        return iterator

    async def run_agent(
        self,
        messages: list[ChatMessage],
        strategy: AgentStrategy,
        *,
        config: AgentConfig | None = None,
    ) -> dict[str, Any]:
        """High-level API: Run agent to completion automatically."""
        if config is None:
            config = AgentConfig()

        iterator = self.create_iterator(messages, strategy, config=config)

        result = {
            "output": None,
            "reasoning": "",
            "error": None,
            "success": False,
            "steps": [],
            "observations": [],
            "metadata": {},
        }

        start_time = time.time()

        try:
            async with asyncio.timeout(config.max_execution_time):
                async for step in iterator:
                    if config.return_intermediate:
                        result["steps"].append(step)

                    # Handle different step types
                    if step.type == StepType.FINISH:
                        finish_data = step.data
                        result.update(finish_data.as_dict())
                        result["success"] = True
                        break

                    elif step.type == StepType.ERROR:
                        result["error"] = str(step.data)
                        result["success"] = False
                        if config.early_stopping == "first_error":
                            break

            # If no output set and no error, agent completed without output
            if result["output"] is None and not result["error"]:
                result["output"] = "Agent completed without producing output"
                result["success"] = False

        except TimeoutError:
            result["error"] = "Agent execution timed out"
            result["success"] = False

        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            result["success"] = False

        # Add execution metadata
        result["metadata"] = {
            "execution_time": time.time() - start_time,
            "total_steps": len(iterator.history),
            "observations": len(iterator.observations),
            "strategy": strategy.strategy_name,
            "execution_mode": config.execution_mode.value,
        }

        # Include intermediate data if requested
        if config.return_intermediate:
            result["observations"] = iterator.observations
            result["history"] = iterator.history

        return result

    async def stream_agent(
        self,
        messages: list[ChatMessage],
        strategy: AgentStrategy,
        *,
        config: AgentConfig | None = None,
        on_action: Callable[[AgentAction], bool] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream agent execution events in real-time."""
        if config is None:
            config = AgentConfig()

        # For streaming, we want automatic execution with real-time events
        # Use the requested execution mode (don't force GUIDED)
        stream_config = AgentConfig(
            execution_mode=config.execution_mode,  # Respect user's choice
            executor_config=config.executor_config,
            max_execution_time=config.max_execution_time,
            max_actions_per_minute=config.max_actions_per_minute,
            early_stopping=config.early_stopping,
            return_intermediate=config.return_intermediate,
        )

        iterator = self.create_iterator(
            messages, strategy, config=stream_config, on_action=on_action
        )

        pending_actions = []
        start_time = time.time()

        try:
            async for step in iterator:
                yield {
                    "type": f"agent_{step.type.value}",
                    "data": self._serialize_step(step),
                    "timestamp": step.timestamp,
                    "metadata": step.metadata,
                }

                if step.type == StepType.ACTION:
                    action = step.data
                    pending_actions.append(action)

                # Observations will be yielded automatically by the iterator
                # in AUTO mode, or can be handled via guided confirmation in GUIDED mode

                elif step.type == StepType.FINISH:
                    # Yield final summary
                    yield {
                        "type": "agent_complete",
                        "data": {
                            "output": step.data.output,
                            "reasoning": step.data.reasoning,
                            "success": True,
                            "execution_time": time.time() - start_time,
                            "total_steps": len(iterator.history),
                            "actions_taken": len(pending_actions),
                        },
                        "timestamp": time.time(),
                        "metadata": {"final": True},
                    }
                    break

                elif step.type == StepType.ERROR:
                    yield {
                        "type": "agent_error",
                        "data": {
                            "error": str(step.data),
                            "recoverable": getattr(step.data, "recoverable", False),
                            "execution_time": time.time() - start_time,
                        },
                        "timestamp": time.time(),
                        "metadata": {"error": True},
                    }

                    if config.early_stopping == "first_error":
                        break

        except Exception as e:
            yield {
                "type": "agent_error",
                "data": {
                    "error": f"Unexpected error: {e}",
                    "execution_time": time.time() - start_time,
                },
                "timestamp": time.time(),
                "metadata": {"unexpected_error": True},
            }

    def _serialize_step(self, step: AgentStep) -> dict[str, Any]:
        """Serialize step data for streaming/API consumption."""
        if step.type == StepType.ACTION:
            action = step.data
            return {
                "id": action.id,
                "tool": action.tool,
                "tool_input": action.tool_input,
                "reasoning": action.reasoning,
                "status": action.status.value,
            }

        elif step.type == StepType.OBSERVATION:
            obs = step.data
            return {
                "action_id": obs.action_id,
                "tool": obs.tool,
                "output": obs.output,
                "success": obs.success,
                "execution_time": obs.execution_time,
                "error": str(obs.error) if obs.error else None,
            }

        elif step.type == StepType.FINISH:
            finish = step.data
            return finish.as_dict()

        elif step.type == StepType.ERROR:
            return {
                "error": str(step.data),
                "error_type": type(step.data).__name__,
                "recoverable": getattr(step.data, "recoverable", False),
            }

        elif step.type == StepType.PLANNING:
            if hasattr(step.data, "content"):
                return {"reasoning": step.data.content}
            return {"data": str(step.data)}

        # Fallback
        return {"data": str(step.data)}
