"""Native graph routing over portable Program data."""

from pydantic import JsonValue
from runengine.invocation.errors import InvocationContractError

from lumora.executions.adapters.run_engine.outbound.errors import application_errors
from lumora.executions.adapters.run_engine.shared.state import ProgramGraphState
from lumora.programs.domain.bindings import project
from lumora.programs.domain.models import ResultRoute
from lumora.programs.domain.routing import RouteSelectionError, normalize_route_selection

__runengine_contract__ = "lumora-result-routing-v1"


@application_errors
async def evaluate_result(
    state: ProgramGraphState, *, route: dict[str, JsonValue]
) -> str | list[str]:
    configured = ResultRoute.model_validate(route)
    value = project(configured.selection, state.serialize())
    try:
        return normalize_route_selection(value, configured.branches)
    except RouteSelectionError as error:
        raise InvocationContractError(str(error)) from None
