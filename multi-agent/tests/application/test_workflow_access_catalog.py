"""Discovery is owner-filtered metadata; it neither issues nor authorizes capabilities."""

import json
from unittest.mock import create_autospec

import pytest
from jsonschema import Draft202012Validator
from mas.application.access.admission import WorkflowAccessIssuer, WorkflowAccessService
from mas.application.access.catalog import WorkflowAccessDescriptor
from mas.application.access.executions import ExecutionGrantAuthority
from mas.application.access.issuance import CredentialIssuance
from mas.application.artifacts.workflow_access import ArtifactWorkflowAccessService
from mas.application.execution.models import StartExecution
from mas.application.reviews.access import ReviewAccessRepository, ReviewAccessService
from mas.application.verification.access import VerificationAccessService
from mas.application.verification.ports import VerificationAccessRepository
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess
from mas.domain.programs.models import ProgramRef
from support.artifact_workflow import MemoryArtifactWorkflowRepository
from support.credential_material import MemoryCredentialMaterial
from support.reviews import review_policy
from support.verification import verification_policy


def test_catalog_reuses_request_contracts_without_root_or_side_effects():
    owner = Identity.user("owner")
    authority = create_autospec(ExecutionGrantAuthority, instance=True)
    reviews = create_autospec(ReviewAccessRepository, instance=True)
    checks = create_autospec(VerificationAccessRepository, instance=True)
    artifacts, material = MemoryArtifactWorkflowRepository(), MemoryCredentialMaterial()
    service = WorkflowAccessService(
        (
            ReviewAccessService(
                reviews, {"release@1": review_policy(owner)}, execution_authority=authority
            ),
            VerificationAccessService(
                checks, {"release@1": verification_policy(owner)}, execution_authority=authority
            ),
            ArtifactWorkflowAccessService(
                artifacts,
                execution_authority=authority,
                issuance=CredentialIssuance("artifact@1", material),
                max_bytes=4096,
            ),
        )
    )
    described = {item.purpose: item for item in service.describe(owner)}
    assert set(described) == {"artifact@1", "review@1", "verification@1"}
    for item in described.values():
        Draft202012Validator.check_schema(item.request_schema)
        assert "root_execution_id" not in json.dumps(item.request_schema)
    for purpose, action in (("review@1", "open"), ("verification@1", "create")):
        schema = described[purpose].request_schema
        Draft202012Validator(schema).validate(
            {"scope": {"policies": ["release@1"], "actions": [action]}, "ttl_seconds": 60}
        )
        assert not Draft202012Validator(schema).is_valid(
            {"scope": {"policies": ["private@1"], "actions": [action]}, "ttl_seconds": 60}
        )
    artifact_schema = described["artifact@1"].request_schema
    valid = {
        "scope": {"namespaces": ["project"], "actions": ["publish"], "max_bytes": 4096},
        "ttl_seconds": 60,
    }
    Draft202012Validator(artifact_schema).validate(valid)
    assert not Draft202012Validator(artifact_schema).is_valid(
        {**valid, "scope": {**valid["scope"], "max_bytes": 4097}}
    )
    assert [item.purpose for item in service.describe(Identity.team(owner.id))] == ["artifact@1"]
    assert not reviews.mock_calls and not checks.mock_calls and not authority.mock_calls
    assert not artifacts.records and not material.reservations and not material.credentials
    request = StartExecution(
        program=ProgramRef(program_id="program", revision=1),
        execution_id="new-root",
        workflow_access=(
            WorkflowAccess(
                purpose="review@1", scope={"policies": ["release@1"], "actions": ["open"]}
            ),
        ),
    )
    with pytest.raises(PermissionError):
        service.approve(request, Identity.team(owner.id), owner)
    assert not artifacts.records and not material.reservations and not material.credentials


def test_new_issuer_is_discoverable_without_catalog_conditionals():
    issuer = create_autospec(WorkflowAccessIssuer, instance=True)
    issuer.purpose = "custom@1"
    issuer.describe_workflow_access.return_value = WorkflowAccessDescriptor(
        purpose=issuer.purpose,
        name="Custom capability",
        description="Installed extension",
        request_schema={"type": "object"},
    )
    service = WorkflowAccessService((issuer,))
    assert service.describe(Identity.user("owner"))[0].purpose == "custom@1"
    issuer.authorize_workflow_access.assert_not_called()
    issuer.provision_workflow_access.assert_not_called()
    issuer.describe_workflow_access.return_value = (
        issuer.describe_workflow_access.return_value.model_copy(update={"purpose": "different@1"})
    )
    with pytest.raises(ValueError):
        service.describe(Identity.user("owner"))
