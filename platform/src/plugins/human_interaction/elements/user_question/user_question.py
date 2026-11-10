"""
User Question Node - Workflow Initiator

Converts user input into tasks and broadcasts to agent network.
Uses clean task-based architecture with agentic threading.
"""

import logging
from typing import ClassVar

from lumora.elements.messaging.domain.messages import ChatMessage, Role
from lumora.elements.node import BaseNode
from lumora.elements.workloads.domain import Task
from lumora.elements.workloads.domain.thread import ThreadStatus
from lumora.programs.graph.capabilities.messaging import GraphMessagingMixin
from lumora.programs.graph.capabilities.workloads import GraphWorkloadMixin
from lumora.programs.graph.state.graph_state import Channel
from lumora.programs.graph.state.state_view import StateView

logger = logging.getLogger(__name__)


class UserQuestionNode(GraphWorkloadMixin, GraphMessagingMixin, BaseNode):
    """
    Workflow initiator that processes user input.

    Enhanced workload management design:
    1. Create thread and workspace for workflow
    2. Copy conversation history to workspace
    3. Convert user input to public conversation
    4. Create agentic task with proper threading
    5. Broadcast task to all adjacent nodes to start workflows
    """

    # Channel permissions - includes workload channels
    READS: ClassVar[set[str]] = {Channel.USER_PROMPT, Channel.MESSAGES}
    WRITES: ClassVar[set[str]] = {Channel.MESSAGES}

    def __init__(self, *, name: str = "user_question", **kwargs):
        super().__init__(**kwargs)
        self.name = name

    async def run(self, state: StateView) -> StateView:
        """Main execution - initiate workflow for user query."""
        prompt = state[Channel.USER_PROMPT]

        if not prompt or not prompt.strip():
            return state

        user_query = prompt.strip()

        # Create thread, workspace, and initiate workflow
        self._initiate_workflow(user_query, state)

        # Promote to public conversation (idempotent — skip if already staged)
        if not self._is_already_staged(state, user_query):
            user_message = ChatMessage(role=Role.USER, content=user_query)
            self.promote_to_messages(user_message)

        return state

    @staticmethod
    def _is_already_staged(state: StateView, user_query: str) -> bool:
        """Check whether this turn's prompt was already staged into messages.

        Looks at the last message only — the projector always appends at
        the end, and a user can legitimately repeat the same prompt in
        a later turn (so scanning the entire history would be wrong).

        Handles both ChatMessage objects and plain dicts (defensive against
        deserialization edge cases).
        """
        msgs = state.get(Channel.MESSAGES, [])
        if not msgs:
            return False
        last = msgs[-1]
        if isinstance(last, dict):
            return (
                last.get("role") in (Role.USER, Role.USER.value)
                and last.get("content") == user_query
            )
        return hasattr(last, "role") and last.role == Role.USER and last.content == user_query

    def _initiate_workflow(self, user_query: str, state: StateView) -> None:
        """
        Create or reuse thread, workspace, and broadcast task to start workflow.

        Enhanced workload management with thread reuse:
        1. Check for existing active thread by this initiator (user question node)
        2. Reuse existing thread if found (conversation continuity)
        3. Create new thread if none exists
        4. Copy conversation history to workspace
        5. Add workflow facts to workspace
        6. Create and broadcast task with thread context

        Thread reuse ensures:
        - Conversation continuity across multiple user inputs
        - Orchestrator can reference previous work plans
        - Context accumulates over the session
        """
        # Try to find existing active thread for this user question node
        existing_threads = self.threads.list_threads_by_initiator(self.uid)
        active_thread = None

        # Find most recent active root thread
        for thread in existing_threads:
            if thread.status == ThreadStatus.ACTIVE and not thread.parent_thread_id:
                # Found an active root thread initiated by this node
                active_thread = thread
                logger.info(
                    "session.thread_reuse",
                    extra={"node_uid": self.uid, "thread_id": thread.thread_id},
                )
                break

        if active_thread:
            # Reuse existing thread
            thread = active_thread
        else:
            # Create new thread for this workflow
            thread = self.threads.create_root_thread(
                title="User Query Processing",
                objective=f"Process user query: {user_query[:50]}...",
                initiator=self.uid,
            )
            logger.info(
                "session.thread_created",
                extra={"node_uid": self.uid, "thread_id": thread.thread_id},
            )

        # Copy current conversation to workspace using new SOLID API
        self.copy_messages_to_workspace(thread.thread_id)

        # Add workflow context to workspace
        self.workspaces.add_fact(thread.thread_id, f"User query: {user_query}")
        self.workspaces.add_fact(thread.thread_id, f"Initiated by: {self.uid}")
        self.workspaces.set_variable(thread.thread_id, "workflow_type", "user_query_processing")
        self.workspaces.set_variable(thread.thread_id, "initiator", self.uid)

        # Create clean, minimal task
        task = Task.create(
            content=user_query,
            should_respond=False,  # No direct response needed
            thread_id=thread.thread_id,
            created_by=self.uid,
        )

        # Broadcast to all adjacent nodes
        self.broadcast_task(task)

        # Log workflow initiation with enhanced context
        if active_thread:
            logger.info(
                "session.thread_reuse",
                extra={"node_uid": self.uid, "thread_id": thread.thread_id, "continued": True},
            )
        else:
            logger.info(
                "session.thread_created",
                extra={
                    "node_uid": self.uid,
                    "thread_id": thread.thread_id,
                    "workflow_initiated": True,
                },
            )
