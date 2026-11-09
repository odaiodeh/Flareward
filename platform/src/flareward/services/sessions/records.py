"""Persisted interaction around published Program executions.

Structured state is independent of graph channels. The optional graph_state is
owned by the conversation projection and is absent for ordinary data Sessions.
No executable graph, provider client or constructed element is stored here.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from flareward.executions.domain.access import WorkflowAccessApproval
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.models import StartExecution
from flareward.programs.domain.models import Bindings, ProgramRef
from flareward.programs.graph.state.graph_state import GraphState
from flareward.services.identity.domain import Identity
from flareward.services.sessions.domain.models import SessionMeta
from flareward.services.sessions.domain.status import SessionStatus


class SessionInteraction(StrEnum):
    DATA = "data"
    CONVERSATION = "conversation"


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    identity: Identity
    blueprint_id: str = ""
    run_context: ExecutionContext
    metadata: SessionMeta = Field(default_factory=SessionMeta)
    interaction: SessionInteraction = SessionInteraction.DATA
    state: dict[str, JsonValue] = Field(default_factory=dict)
    graph_state: GraphState | None = None
    status: SessionStatus = SessionStatus.PENDING
    program: ProgramRef | None = None
    version: int = Field(default=0, ge=0)
    active_execution_id: str | None = None
    execution_request: StartExecution | None = None
    workflow_access_approval: WorkflowAccessApproval | None = None
    active_inputs: dict[str, JsonValue] = Field(default_factory=dict)
    cancellation_requested: bool = False
    approval_rules_revision: int = Field(default=0, ge=0)
    input_bindings: Bindings = Field(default_factory=dict)
    output_bindings: Bindings = Field(default_factory=dict)
    last_result: JsonValue = None

    @property
    def engine_handle(self) -> str | None:
        """The background workflow handle (Temporal workflow ID, Celery task ID, etc.)."""
        return self.run_context.engine_handle

    def update_context(self, **updates: JsonValue) -> None:
        """Apply updates to the frozen ExecutionContext."""
        self.run_context = self.run_context.model_copy(update=updates)
