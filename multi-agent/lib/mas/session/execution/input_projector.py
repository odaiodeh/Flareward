"""Legacy persistence adapter for shared session turn staging."""

from pydantic import JsonValue

from mas.session.domain.session_record import SessionRecord
from mas.session.execution.staging import stage_inputs
from mas.session.repository.repository import SessionRepository


class SessionInputProjector:
    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def apply(
        self,
        record: SessionRecord,
        inputs: dict[str, JsonValue],
        logged_in_user: str = "",
    ) -> None:
        stage_inputs(record, inputs, logged_in_user)
        self._repo.save(record)
