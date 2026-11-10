"""Stage one interaction turn without imposing a graph input contract."""

from pydantic import JsonValue

from lumora.executions.domain.context import APPROVAL_RULES_TAG
from lumora.services.interactions.models import parse_approval_rules
from lumora.services.sessions.domain.constants import CANCELLED_TAG
from lumora.services.sessions.domain.status import SessionStatus
from lumora.services.sessions.execution.projection import SessionProjection
from lumora.services.sessions.records import SessionRecord
from lumora.services.sessions.title import derive_title


def stage_inputs(
    record: SessionRecord,
    inputs: dict[str, JsonValue],
    credential_user_id: str = "",
) -> None:
    if record.metadata.title is None:
        record.metadata.title = derive_title(inputs)
    SessionProjection.stage(record, inputs, credential_user_id)
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
