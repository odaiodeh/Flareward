"""Existing agents with a deterministic LLM and context-bound tool evidence."""

import hashlib
import json
import re
from collections.abc import AsyncGenerator
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from lumora.elements.construction.context import ElementBuildContext
from lumora.elements.factory import BaseFactory
from lumora.elements.messaging.domain.messages import ChatMessage, Role, ToolCall
from lumora.elements.ports.llm import BaseLLM
from lumora.elements.ports.tool import BaseTool
from lumora.elements.specification import BaseElementSpec
from lumora.elements.tools.domain.models import ToolDefinition
from lumora.executions.domain.context import ExecutionContext
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.references import ToolRef
from plugins.agents.elements.custom_agent.spec.spec import CustomAgentNodeElementSpec
from plugins.human_interaction.elements.user_question.spec.spec import (
    UserQuestionNodeElementSpec,
)
from plugins.mas.elements.final_answer.spec.spec import FinalAnswerNodeElementSpec
from support.elements import DependencySpec, TextResource

__runengine_contract__ = "lumora-test-agent-session-v1"


class AgentRole(StrEnum):
    RESEARCH = "research"
    REVIEW = "review"


class EvidenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: ToolRef
    role: AgentRole


class EvidenceArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceTool(BaseTool):
    args_schema = EvidenceArguments

    def __init__(self, source: TextResource, role: AgentRole, context: ExecutionContext) -> None:
        self._source, self._role, self._context = source, role, context
        self.name = f"read_{role.value}_evidence"
        self.description = (
            "Read fresh evidence for this execution; include its evidence token in the answer."
        )

    async def run(self) -> str:
        leaf = self._source.dependency
        if leaf is None:
            raise ValueError("Evidence requires its transitive data dependency")
        digest = hashlib.sha256(
            f"{leaf.value}:{self._context.execution_id}:{self._role.value}".encode()
        ).hexdigest()
        return json.dumps(
            {
                "role": self._role.value,
                "evidence": digest,
                "execution_id": self._context.execution_id,
                "session_id": self._context.session_id,
                "source": self._source.value,
            }
        )


class EvidenceFactory(BaseFactory):
    def accepts(self, cfg: EvidenceConfig, element_type: str) -> bool:
        return element_type == "platform_session_evidence"

    def create(self, cfg: EvidenceConfig, **dependencies) -> EvidenceTool:
        context: ElementBuildContext = dependencies["deps"]
        if context.execution_ctx is None:
            raise ValueError("Evidence requires an execution context")
        return EvidenceTool(dependencies["source"], cfg.role, context.execution_ctx.context)


class EvidenceSpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = "platform_session_evidence"
    name = "Session evidence"
    description = "A real agent tool with shared transitive dependencies and execution identity"
    config_schema = EvidenceConfig
    factory_cls = EvidenceFactory


class ScriptedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScriptedLLM(BaseLLM):
    """Only tool results supply fresh evidence; prior messages supply earlier evidence."""

    def __init__(self, tools: tuple[ToolDefinition, ...] = ()) -> None:
        self._tools = tools

    @property
    def name(self) -> str:
        return "scripted-session-model"

    def bind_tools(self, tools: list[ToolDefinition]) -> ScriptedLLM:
        return ScriptedLLM(tuple(tools))

    async def chat(self, messages: list[ChatMessage]) -> ChatMessage:
        tool = next(tool for tool in self._tools if tool.name.startswith("read_"))
        observation = next(
            (message for message in reversed(messages) if message.role == Role.TOOL), None
        )
        if observation is None:
            return ChatMessage(
                role=Role.ASSISTANT,
                content="Read the evidence before producing the answer.",
                tool_calls=[ToolCall(name=tool.name, args={}, tool_call_id=tool.name)],
            )
        evidence = json.loads(observation.content)
        previous = dict.fromkeys(
            token
            for message in messages
            if message.role != Role.TOOL
            for token in re.findall(r"\b[0-9a-f]{64}\b", message.content)
        )
        return ChatMessage(
            role=Role.ASSISTANT,
            content="Verified evidence: "
            + json.dumps({**evidence, "context_evidence": list(previous)}),
        )

    async def stream(
        self, messages: list[ChatMessage], **call_params
    ) -> AsyncGenerator[str | ChatMessage]:
        response = await self.chat(messages)
        if not response.tool_calls:
            yield response.content
        yield response


class ScriptedFactory(BaseFactory):
    def accepts(self, cfg: ScriptedConfig, element_type: str) -> bool:
        return element_type == "platform_session_llm"

    def create(self, cfg: ScriptedConfig, **dependencies) -> ScriptedLLM:
        return ScriptedLLM()


class ScriptedSpec(BaseElementSpec):
    category = ResourceCategory.LLM
    type_key = "platform_session_llm"
    name = "Scripted session model"
    description = "Deterministic tool calling through the existing agent loop"
    config_schema = ScriptedConfig
    factory_cls = ScriptedFactory


ELEMENT_SPECIFICATIONS = (
    DependencySpec,
    EvidenceSpec,
    ScriptedSpec,
    CustomAgentNodeElementSpec,
    UserQuestionNodeElementSpec,
    FinalAnswerNodeElementSpec,
)


def session_blueprint(researcher: str, reviewer: str) -> dict:
    return {
        "name": "Research and review session",
        "nodes": [
            {"rid": "question", "name": "Question", "type": "user_question_node", "config": {}},
            {"rid": "$ref:" + researcher},
            {"rid": "$ref:" + reviewer},
            {"rid": "answer", "name": "Answer", "type": "final_answer_node", "config": {}},
        ],
        "plan": [
            {"uid": "question", "node": "question"},
            {"uid": "research", "node": "$ref:" + researcher, "after": "question"},
            {"uid": "review", "node": "$ref:" + reviewer, "after": "research"},
            {"uid": "answer", "node": "answer", "after": "review"},
        ],
    }
