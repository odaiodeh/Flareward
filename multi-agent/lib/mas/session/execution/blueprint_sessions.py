"""Create chat sessions from protected, immutable blueprint program snapshots."""

from uuid import uuid4

from mas.application.programs.blueprints import BlueprintProgramService
from mas.application.programs.service import ProgramService
from mas.core.identity import Identity
from mas.domain.programs.models import Bindings, PathBinding
from mas.graph.state.graph_state import GraphState
from mas.session.domain.models import SessionMeta
from mas.session.domain.session_record import SessionInteraction, SessionRecord
from mas.session.execution.program_sessions import CreateProgramSession, ProgramSessionService


class BlueprintSessionService:
    def __init__(
        self,
        blueprints: BlueprintProgramService,
        programs: ProgramService,
        sessions: ProgramSessionService,
    ) -> None:
        self._blueprints, self._programs, self._sessions = blueprints, programs, sessions

    async def create(
        self, blueprint_id: str, caller: Identity, *, metadata: SessionMeta
    ) -> SessionRecord:
        # A unique draft identity prevents concurrent sessions publishing each other's snapshot.
        program_id = "session-snapshot-" + uuid4().hex
        draft = await self._blueprints.save(blueprint_id, program_id, caller)
        revision = await self._programs.publish(program_id, caller, expected_version=draft.version)
        bindings: Bindings = {name: PathBinding(path=(name,)) for name in GraphState.model_fields}
        return await self._sessions.create(
            CreateProgramSession(
                program=revision.reference,
                interaction=SessionInteraction.CONVERSATION,
                blueprint_id=blueprint_id,
                metadata=metadata,
                input_bindings=bindings,
                output_bindings=bindings,
            ),
            caller,
        )
