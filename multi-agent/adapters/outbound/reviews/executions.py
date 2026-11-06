"""Bind review occurrences to accepted application executions through public service ports."""

from mas.application.execution.ports import ExecutionError, ExecutionMissing
from mas.application.execution.service import ExecutionService
from mas.application.reviews.ports import ReviewMissing, ReviewUnavailable
from mas.core.identity import Identity
from mas.domain.reviews import ReviewRecord


class ExecutionReviews:
    def __init__(self, executions: ExecutionService) -> None:
        self._executions = executions

    async def active(self, execution_id: str, root_execution_id: str, owner: Identity) -> bool:
        try:
            root = await self._executions.get(root_execution_id, owner)
            if (
                root.context.root_execution_id != root_execution_id
                or root.parent_execution_id is not None
            ):
                raise ReviewMissing("Review execution not found")
            try:
                record = await self._executions.get(execution_id, owner)
            except KeyError:
                # A child may have begun before the API has projected its accepted request.
                await self._executions.children(root_execution_id, owner)
                record = await self._executions.get(execution_id, owner)
            if record.context.root_execution_id != root_execution_id:
                raise ReviewMissing("Review execution not found")
            return await self._executions.is_active(
                root_execution_id, owner
            ) and await self._executions.is_active(execution_id, owner)
        except PermissionError:
            raise ReviewMissing("Review execution not found") from None
        except KeyError, ExecutionMissing, ExecutionError:
            raise ReviewUnavailable() from None

    async def wake(self, review: ReviewRecord) -> None:
        await self._executions.send(
            review.execution_id, review.message_name, {"review_id": review.review_id}, review.owner
        )
