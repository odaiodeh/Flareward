"""ReAct (Reasoning + Acting) agent strategy."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from flareward.elements.agents.constants import (
    ErrorMessages,
    StrategyDefaults,
    StrategyType,
    SystemPrompts,
)
from flareward.elements.agents.domain.models import AgentFinish, AgentStep, StepType
from flareward.elements.agents.parsers import OutputParser, ParseError, ParseErrorType
from flareward.elements.agents.strategies.base import AgentStrategy
from flareward.elements.messaging.domain.messages import ChatMessage, Role
from flareward.elements.ports.tool import BaseTool


class ReActStrategy(AgentStrategy):
    """ReAct strategy implementation."""

    def __init__(
        self,
        *,
        llm_chat: Callable[[list[ChatMessage], list[BaseTool]], Awaitable[ChatMessage]],
        tools: list[BaseTool],
        parser: OutputParser,
        max_steps: int = StrategyDefaults.MAX_STEPS,
        system_prompt_template: str | None = None,
        min_reasoning_length: int = StrategyDefaults.MIN_REASONING_LENGTH,
        system_message: str | None = None,
    ):
        """Initialize ReAct strategy."""
        super().__init__(
            llm_chat=llm_chat,
            tools=tools,
            parser=parser,
            max_steps=max_steps,
            system_message=system_message,
        )
        self.min_reasoning_length = min_reasoning_length
        self.system_prompt_template = system_prompt_template or SystemPrompts.REACT_DEFAULT

    @property
    def strategy_name(self) -> str:
        """Return the name of this strategy."""
        return StrategyType.REACT.value

    def get_tools_for_phase(self, phase: str, context: dict[str, Any] = None) -> list[BaseTool]:
        """ReAct uses all tools in all phases."""
        return list(self.all_tools.values())

    async def think(self, messages: list[ChatMessage]) -> list[AgentStep]:
        """ReAct thinking with error handling."""
        try:
            # Build context
            context = self.build_context(messages)
            tools = self.get_tools_for_phase(StrategyType.REACT.value)

            # Get LLM response
            start_time = time.time()
            response = await self.llm_chat(context, tools)
            reasoning_time = time.time() - start_time

            # Parse response
            result = self.parser.parse(response)

            # Validate reasoning only for final answers (AgentFinish)
            # Tool calls (List[AgentAction]) don't need reasoning validation
            if isinstance(result, AgentFinish):
                self._validate_reasoning(response)

            # Success - reset error count
            self._error_count = 0

            # Return appropriate steps
            steps = self._create_success_steps(response, result, reasoning_time)

        except ParseError as e:
            # Add error feedback to messages
            error_feedback = ChatMessage(
                role=Role.SYSTEM, content=ErrorMessages.get_parse_error_guidance(e)
            )
            messages.append(error_feedback)

            steps = [self._create_error_step(e, "parse_error")]

        except Exception as e:
            error_feedback = ChatMessage(
                role=Role.SYSTEM, content=f"System error: {e}. Try a different approach."
            )
            messages.append(error_feedback)

            steps = [self._create_error_step(e, "strategy_error")]

        self.increment_step_count()
        return steps

    def should_continue(self, history: list[AgentStep]) -> bool:
        """Check if ReAct strategy should continue."""
        # Check for terminal steps
        if history and history[-1].is_terminal:
            return False

        # Check step limit
        if self._step_count >= self.max_steps:
            return False

        # Check for too many consecutive errors
        consecutive_errors = 0
        for step in reversed(history):
            if step.is_error():
                consecutive_errors += 1
            else:
                break

        if consecutive_errors >= 3:  # Configurable threshold
            return False

        return True

    def build_context(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Build context for ReAct strategy."""
        context = self._build_base_context(messages)
        # Messages already include TOOL messages - no need to re-process
        return context

    def _validate_reasoning(self, response: ChatMessage) -> None:
        """Validate the quality of reasoning in final answers."""
        content = response.content or ""

        # Check minimum length
        if len(content) < self.min_reasoning_length:
            raise ParseError(
                f"Reasoning too short ({len(content)} chars, min {self.min_reasoning_length})",
                ParseErrorType.VALIDATION_ERROR,
                content,
                recoverable=True,
            )

        # Could add more sophisticated reasoning quality checks here
        # - Presence of reasoning keywords
        # - Analysis of current situation
        # - Clear action justification

    def _build_base_context(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Build base context with system message."""
        context = list(messages)

        system_content = self.system_message or self.system_prompt_template
        if context and context[0].role == Role.SYSTEM:
            context[0] = ChatMessage(role=Role.SYSTEM, content=system_content)
        else:
            context.insert(0, ChatMessage(role=Role.SYSTEM, content=system_content))

        return context

    def _create_success_steps(
        self, response: ChatMessage, result, reasoning_time: float
    ) -> list[AgentStep]:
        """Create steps for successful execution."""

        steps = [
            AgentStep(
                type=StepType.PLANNING,
                data=response,
                metadata={
                    "strategy": StrategyType.REACT.value,
                    "step_count": self._step_count,
                    "reasoning_time": reasoning_time,
                    "reasoning_content": response.content,
                },
            )
        ]

        if isinstance(result, list):
            action_steps = [
                AgentStep(
                    type=StepType.ACTION,
                    data=action,
                    metadata={
                        "strategy": StrategyType.REACT.value,
                        "reasoning": response.content or "",
                        "step_count": self._step_count,
                    },
                )
                for action in result
            ]
            steps.extend(action_steps)
        else:
            steps.append(
                AgentStep(
                    type=StepType.FINISH,
                    data=result,
                    metadata={
                        "strategy": StrategyType.REACT.value,
                        "reasoning": response.content or "",
                        "step_count": self._step_count,
                    },
                )
            )

        return steps

    def _create_error_step(self, error: Exception, error_type: str) -> AgentStep:
        """Create clean error step."""
        return AgentStep(
            type=StepType.ERROR,
            data=error,
            metadata={
                "strategy": StrategyType.REACT.value,
                "error_type": error_type,
                "step_count": self._step_count,
                "recoverable": getattr(error, "recoverable", error_type == "parse_error"),
            },
        )
