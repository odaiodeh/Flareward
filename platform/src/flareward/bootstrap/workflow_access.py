"""One composition of workflow authority for API submission and trusted tick admission."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from flareward.bootstrap.settings.workflow_access_settings import WorkflowAccessSettings
from flareward.services.access.adapters.mongo.artifact_workflow_access import (
    MongoArtifactWorkflowRepository,
)
from flareward.services.access.adapters.mongo.credential_material import MongoCredentialMaterial
from flareward.services.access.adapters.mongo.workflow_consents import MongoWorkflowConsents
from flareward.services.access.admission import WorkflowAccessIssuer, WorkflowAccessService
from flareward.services.access.consent import WorkflowConsents
from flareward.services.access.executions import ExecutionGrantAuthority
from flareward.services.access.issuance import (
    CredentialDelivery,
    CredentialIssuance,
    CredentialMaterialRetirement,
    ManagedCredentialOwner,
)
from flareward.services.artifacts.workflow_access import ArtifactWorkflowAccessService
from flareward.services.auth.adapters.crypto import FieldCipher
from flareward.services.reviews.access import ReviewAccessService
from flareward.services.reviews.adapters.mongo.reviews import MongoReviewAccessRepository
from flareward.services.verification.access import VerificationAccessService
from flareward.services.verification.adapters.mongo.verification_access import (
    MongoVerificationAccessRepository,
)


@dataclass(frozen=True)
class WorkflowAccessComponents:
    reviews: ReviewAccessService | None
    verifications: VerificationAccessService | None
    artifacts: ArtifactWorkflowAccessService | None
    admission: WorkflowAccessService | None
    consents: WorkflowConsents | None
    retirement: CredentialMaterialRetirement | None

    @classmethod
    async def create(
        cls,
        settings: WorkflowAccessSettings,
        database: AsyncDatabase[dict[str, Any]] | None,
        authority: ExecutionGrantAuthority,
    ) -> WorkflowAccessComponents:
        material = None
        delivery: CredentialDelivery | None = None
        if settings.recoverable_credential_issuance:
            settings.validate_workflow_key()
            if database is None:
                raise ValueError("Recoverable workflow access requires durable storage")
            material = MongoCredentialMaterial(
                database, FieldCipher(settings.credential_encryption_key.get_secret_value())
            )
            await material.initialize()
            if settings.workflow_credential_directory is not None:
                delivery = import_module(
                    "flareward.services.access.adapters.workflow_credentials"
                ).FileWorkflowCredentials(settings.workflow_credential_directory)
        reviews = None
        if settings.reviews_enabled:
            assert database is not None
            review_repository = MongoReviewAccessRepository(database)
            await review_repository.initialize()
            reviews = ReviewAccessService(
                review_repository,
                settings.review_policies,
                execution_authority=authority,
                issuance=CredentialIssuance(ReviewAccessService.purpose, material, delivery)
                if material is not None
                else None,
            )
        verifications = None
        if settings.verification_enabled:
            assert database is not None
            verification_repository = MongoVerificationAccessRepository(database)
            await verification_repository.initialize()
            verifications = VerificationAccessService(
                verification_repository,
                settings.verification_policies,
                execution_authority=authority,
                issuance=CredentialIssuance(VerificationAccessService.purpose, material, delivery)
                if material is not None
                else None,
            )
        artifacts = None
        if settings.artifact_workflow_enabled:
            if database is None or material is None:
                raise ValueError("Managed artifact access requires durable recoverable issuance")
            artifact_repository = MongoArtifactWorkflowRepository(database)
            await artifact_repository.initialize()
            artifacts = ArtifactWorkflowAccessService(
                artifact_repository,
                execution_authority=authority,
                issuance=CredentialIssuance(
                    ArtifactWorkflowAccessService.purpose, material, delivery
                ),
                max_bytes=settings.artifact_max_bytes,
            )
        issuers: tuple[WorkflowAccessIssuer, ...] = tuple(
            service for service in (reviews, verifications, artifacts) if service is not None
        )
        admission = WorkflowAccessService(issuers) if delivery is not None else None
        consents = (
            WorkflowConsents(MongoWorkflowConsents(database), admission)
            if database is not None and admission is not None
            else None
        )
        purposes: dict[str, ManagedCredentialOwner] = {
            service.purpose: service
            for service in (reviews, verifications, artifacts)
            if service is not None
        }
        retirement = (
            CredentialMaterialRetirement(
                material,
                purposes,
                authority,
                deliveries=(delivery,) if delivery is not None else (),
            )
            if material is not None
            else None
        )
        return cls(reviews, verifications, artifacts, admission, consents, retirement)
