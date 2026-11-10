import logging

from lumora.elements.condition import BaseCondition
from lumora.elements.domain.conditions import BranchType, ConditionOutputSchema, DirectBranchDef
from lumora.programs.graph.messaging import get_outgoing_targets
from lumora.programs.graph.state.graph_state import Channel
from lumora.programs.graph.state.state_view import StateView

logger = logging.getLogger(__name__)


class RouterDirectCondition(BaseCondition):
    """
    IEM-based router condition that routes to nodes receiving packets.
    """

    READS = {Channel.INTER_PACKETS}

    def run(self, state: StateView) -> str | tuple[str, ...]:
        """
        Route to nodes that have been receiving packets from this node.

        Returns:
            - Node UID(s) if targets exist
            - END label if no targets; the graph must explicitly declare its destination
        """
        if self.context is None:
            raise RuntimeError("Direct routing requires a step context")

        targets = sorted(get_outgoing_targets(state, self.context))
        logger.info("graph.router_targets", extra={"targets": targets})
        if not targets:
            logger.warning("graph.router_no_targets")
            return "END"

        if len(targets) == 1:
            return targets[0]

        # Return as tuple for multiple targets
        return tuple(targets)

    def __repr__(self) -> str:
        return "<RouterDirectCondition: IEM-based routing>"

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        """
        RouterDirectCondition returns direct node UIDs based on IEM analysis.
        """
        return ConditionOutputSchema(
            branch_type=BranchType.DIRECT,
            direct_config=DirectBranchDef(
                description="Routes to IEM recipients; declare an END destination for no recipients"
            ),
            description="IEM-based router that follows actual packet communication",
        )
