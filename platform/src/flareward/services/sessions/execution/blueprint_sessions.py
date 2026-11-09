"""Create chat sessions from protected, immutable blueprint program snapshots."""

from uuid import uuid4

from flareward.programs.blueprints import BlueprintProgramService
from flareward.programs.domain.models import Bindings, PathBinding
from flareward.programs.graph.state.graph_state import GraphState
from flareward.programs.service import ProgramService
from flareward.services.identity.domain import Identity
from flareward.services.sessions.domain.models import SessionMeta
from flareward.services.sessions.execution.program_sessions import (
    CreateProgramSession,
    ProgramSessionService,
)
from flareward.services.sessions.records import SessionInteraction, SessionRecord


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
