"""Approve explicit root capabilities, then provision them inside submission ownership."""

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from typing import Protocol

from flareward.executions.domain.access import WorkflowAccess, WorkflowAccessApproval
from flareward.executions.domain.models import ExecutionFailure, ExecutionRecord, FailureKind
from flareward.executions.models import StartExecution
from flareward.executions.ports import ExecutionError, SubmissionUnconfirmed
from flareward.services.access.catalog import WorkflowAccessDescriptor
from flareward.services.access.credentials import WorkflowCredentialUnavailable
from flareward.services.identity.domain import Identity


def access_request_digest(request: StartExecution) -> str:
    value = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(value.encode()).hexdigest()


def check_access_approval(
    request: StartExecution, owner: Identity, approval: WorkflowAccessApproval
) -> None:
    if (
        not approval.owner.owns(owner)
        or approval.root_execution_id != request.execution_id
        or approval.request_sha256 != access_request_digest(request)
        or approval.requirements != request.workflow_access
    ):
        raise PermissionError("Workflow access approval does not match the invocation")


class WorkflowAccessIssuer(Protocol):
    purpose: str

    def describe_workflow_access(self, owner: Identity) -> WorkflowAccessDescriptor | None: ...

    def authorize_workflow_access(
        self, requirement: WorkflowAccess, root: str, owner: Identity, issued_by: Identity
    ) -> None: ...
    async def provision_workflow_access(
        self,
        requirement: WorkflowAccess,
        root: str,
        owner: Identity,
        issued_by: Identity,
        *,
        key: str,
    ) -> None: ...


class WorkflowAccessAdmission(Protocol):
    def approve(
        self, request: StartExecution, owner: Identity, approved_by: Identity
    ) -> WorkflowAccessApproval: ...
    async def provision(self, record: ExecutionRecord) -> None: ...


class WorkflowAccessService:
    def __init__(
        self,
        issuers: Sequence[WorkflowAccessIssuer],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._issuers = {issuer.purpose: issuer for issuer in issuers}
        if len(self._issuers) != len(issuers):
            raise ValueError("Workflow access issuer purposes must be unique")
        self._now = clock or partial(datetime.now, UTC)

    def describe(self, owner: Identity) -> tuple[WorkflowAccessDescriptor, ...]:
        descriptors = []
        for purpose, issuer in sorted(self._issuers.items()):
            descriptor = issuer.describe_workflow_access(owner)
            if descriptor is not None:
                if descriptor.purpose != purpose:
                    raise ValueError("Workflow access descriptor does not match its issuer")
                descriptors.append(descriptor)
        return tuple(descriptors)

    def approve(
        self, request: StartExecution, owner: Identity, approved_by: Identity
    ) -> WorkflowAccessApproval:
        if not request.execution_id:
            raise ValueError("Workflow access approval requires an invocation identity")
        approval = WorkflowAccessApproval(
            owner=owner,
            root_execution_id=request.execution_id,
            approved_by=approved_by,
            approved_at=self._now(),
            request_sha256=access_request_digest(request),
            requirements=request.workflow_access,
        )
        for requirement in approval.requirements:
            issuer = self._issuers.get(requirement.purpose)
            if issuer is None:
                raise ValueError(
                    "Workflow access purpose is not configured for managed provisioning"
                )
            issuer.authorize_workflow_access(requirement, request.execution_id, owner, approved_by)
        return approval

    async def provision(self, record: ExecutionRecord) -> None:
        approval = record.workflow_access_approval
        if approval is None:
            return
        try:
            check_access_approval(
                StartExecution(
                    execution_id=record.execution_id,
                    program=record.program,
                    inputs=record.inputs,
                    session_id=record.session_id,
                    workflow_access=approval.requirements,
                ),
                record.owner,
                approval,
            )
            # Validate all purposes before creating any private material.
            for requirement in approval.requirements:
                issuer = self._issuers.get(requirement.purpose)
                if issuer is None:
                    raise WorkflowCredentialUnavailable()
                issuer.authorize_workflow_access(
                    requirement, record.execution_id, record.owner, approval.approved_by
                )
            for requirement in approval.requirements:
                key = hashlib.sha256(
                    json.dumps(
                        [
                            "admitted-root@1",
                            record.owner.type.value,
                            record.owner.id,
                            record.execution_id,
                            approval.request_sha256,
                            requirement.purpose,
                        ],
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                await self._issuers[requirement.purpose].provision_workflow_access(
                    requirement,
                    record.execution_id,
                    record.owner,
                    approval.approved_by,
                    key=key,
                )
        except WorkflowCredentialUnavailable:
            raise SubmissionUnconfirmed(
                ExecutionFailure(
                    kind=FailureKind.INFRASTRUCTURE,
                    message="Workflow access provisioning is pending",
                    code="workflow_access_pending",
                    retryable=True,
                )
            ) from None
        except PermissionError, ValueError:
            raise ExecutionError(
                ExecutionFailure(
                    kind=FailureKind.CONTRACT,
                    message="Approved workflow access is no longer permitted",
                    code="workflow_access_denied",
                )
            ) from None
