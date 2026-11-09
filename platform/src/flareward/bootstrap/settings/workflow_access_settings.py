"""Shared trusted control-plane access policy; ordinary receivers need only their source."""

from base64 import b64decode

from pydantic import Field

from flareward.bootstrap.settings.receiver_settings import ReceiverSettings
from flareward.services.reviews.contracts import ReviewPolicy
from flareward.services.verification.models import VerificationPolicy


class WorkflowAccessSettings(ReceiverSettings):
    reviews_enabled: bool = False
    verification_enabled: bool = False
    artifact_workflow_enabled: bool = False
    artifact_max_bytes: int = Field(default=67_108_864, ge=1, le=1_073_741_824)
    recoverable_credential_issuance: bool = False
    review_policies: dict[str, ReviewPolicy] = Field(default_factory=dict, max_length=128)
    verification_policies: dict[str, VerificationPolicy] = Field(
        default_factory=dict, max_length=128
    )

    def validate_workflow_key(self) -> None:
        if not self.recoverable_credential_issuance:
            return
        if not (
            self.reviews_enabled or self.verification_enabled or self.artifact_workflow_enabled
        ):
            raise ValueError("Recoverable credential issuance requires workflow access services")
        if not self.credential_encryption_key.get_secret_value():
            raise ValueError("Recoverable credential issuance requires an encryption key")
        try:
            valid = (
                len(
                    b64decode(
                        self.credential_encryption_key.get_secret_value(),
                        altchars=b"-_",
                        validate=True,
                    )
                )
                == 32
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Recoverable credential issuance requires a valid encryption key")
