"""Pure turn staging shared by legacy and async session services."""

from pydantic import JsonValue

from mas.core.execution_context import APPROVAL_RULES_TAG
from mas.domain.messages import ChatMessage, Role
from mas.graph.state.graph_state import GraphState
from mas.interactions.models import parse_approval_rules
from mas.session.domain.constants import CANCELLED_TAG
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.session.management.utils import derive_title


def stage_inputs(
    record: SessionRecord,
    inputs: dict[str, JsonValue],
    credential_user_id: str = "",
) -> None:
    if record.metadata.title is None:
        record.metadata.title = derive_title(inputs)
    changes = {name: value for name, value in inputs.items() if name in GraphState.model_fields}
    record.graph_state = GraphState.model_validate({**record.graph_state.serialize(), **changes})
    prompt = inputs.get("user_prompt")
    if isinstance(prompt, str) and prompt.strip():
        record.graph_state.messages.append(
            ChatMessage(
                role=Role.USER,
                content=prompt.strip(),
                sender_id=credential_user_id or None,
            )
        )
    record.run_context = (
        record.run_context.with_credential_user(credential_user_id)
        .with_hitl(record.metadata.hitl_enabled)
        .mark_active()
    )
    record.run_context = record.run_context.model_copy(update={"finished_at": None})
    rules = parse_approval_rules(getattr(record.metadata, "hitl_overrides", None))
    record.run_context = record.run_context.model_copy(
        update={
            "tags": {
                **record.run_context.tags,
                APPROVAL_RULES_TAG: rules.to_dict(),
            }
        }
    )
    record.metadata.status_message = None
    record.metadata.tags.pop(CANCELLED_TAG, None)
    record.status = SessionStatus.QUEUED
