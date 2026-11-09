"""Session data bindings are generic; conversation is an explicit interaction adapter."""

from pydantic import JsonValue

from flareward.elements.messaging.domain.messages import ChatMessage, Role
from flareward.programs.graph.state.graph_state import GraphState
from flareward.services.sessions.records import SessionInteraction, SessionRecord


class SessionProjection:
    @staticmethod
    def conversation(record: SessionRecord) -> GraphState:
        if record.interaction != SessionInteraction.CONVERSATION:
            raise ValueError("Structured Sessions use data state; inspect their Program execution")
        if record.graph_state is None:
            record.graph_state = GraphState()
        return record.graph_state

    @staticmethod
    def validate(interaction: SessionInteraction, outputs: set[str]) -> None:
        if (
            interaction == SessionInteraction.CONVERSATION
            and outputs - GraphState.model_fields.keys()
        ):
            raise ValueError("Conversation output bindings target unknown conversation channels")

    @staticmethod
    def source(record: SessionRecord) -> dict[str, JsonValue]:
        if record.interaction == SessionInteraction.CONVERSATION:
            return SessionProjection.conversation(record).serialize()
        return record.state

    @staticmethod
    def stage(record: SessionRecord, inputs: dict[str, JsonValue], user: str) -> None:
        record.state = {**record.state, **inputs}
        if record.interaction != SessionInteraction.CONVERSATION:
            return
        changes = {name: value for name, value in inputs.items() if name in GraphState.model_fields}
        record.graph_state = GraphState.model_validate(
            {**SessionProjection.conversation(record).serialize(), **changes}
        )
        prompt = inputs.get("user_prompt")
        if isinstance(prompt, str) and prompt.strip():
            SessionProjection.conversation(record).messages.append(
                ChatMessage(role=Role.USER, content=prompt.strip(), sender_id=user or None)
            )

    @staticmethod
    def accept(record: SessionRecord, changes: dict[str, JsonValue]) -> None:
        if record.interaction == SessionInteraction.CONVERSATION:
            SessionProjection.validate(record.interaction, set(changes))
            record.graph_state = GraphState.model_validate(
                {**SessionProjection.conversation(record).serialize(), **changes}
            )
        record.state = {**record.state, **changes}

    @staticmethod
    def cancel(record: SessionRecord) -> None:
        if record.interaction != SessionInteraction.CONVERSATION:
            return
        state = SessionProjection.conversation(record)
        if state.messages:
            last = state.messages[-1]
            state.messages[-1] = last.model_copy(
                update={"metadata": {**last.metadata, "is_cancelled": True}}
            )
