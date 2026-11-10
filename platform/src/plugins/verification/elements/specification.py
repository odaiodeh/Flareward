"""Use ordinary dependency references, schemas and factories for workflow verification."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from lumora.elements.construction.context import ElementBuildContext
from lumora.elements.factory import BaseFactory
from lumora.elements.specification import BaseElementSpec
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.references import ProviderRef
from lumora.services.verification.check_ports import CheckRunHandle, StartCheckRun
from lumora.services.verification.domain.check_runs import CheckRun
from lumora.services.verification.models import VerificationView
from plugins.verification.elements.check_operations import (
    RefreshCheckOperation,
    StartCheckOperation,
)
from plugins.verification.elements.http import (
    HTTPVerificationGateway,
    VerificationTransportSettings,
)
from plugins.verification.elements.operations import (
    CancelVerificationOperation,
    InspectVerificationOperation,
    RequestVerification,
    RequestVerificationOperation,
    VerificationHandle,
)


class VerificationConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    access_token: SecretStr | None = Field(default=None, repr=False, min_length=1)


class VerificationOperationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: ProviderRef


class VerificationConnectionFactory(BaseFactory[VerificationConnection, HTTPVerificationGateway]):
    def accepts(self, cfg: VerificationConnection, element_type: str) -> bool:
        return element_type == "verification_service"

    def create(self, cfg: VerificationConnection, **dependencies: Any) -> HTTPVerificationGateway:
        deps: ElementBuildContext = dependencies["deps"]
        if deps.execution_ctx is None:
            raise ValueError("Verification requires execution identity")
        return HTTPVerificationGateway(
            VerificationTransportSettings.model_validate({}),
            deps.execution_ctx.context,
            cfg.access_token,
            source=deps.workflow_credentials,
        )


class RequestVerificationFactory(
    BaseFactory[VerificationOperationConfig, RequestVerificationOperation]
):
    def accepts(self, cfg: VerificationOperationConfig, element_type: str) -> bool:
        return element_type == "request_verification"

    def create(
        self, cfg: VerificationOperationConfig, **dependencies: Any
    ) -> RequestVerificationOperation:
        return RequestVerificationOperation(dependencies["service"])


class InspectVerificationFactory(
    BaseFactory[VerificationOperationConfig, InspectVerificationOperation]
):
    def accepts(self, cfg: VerificationOperationConfig, element_type: str) -> bool:
        return element_type == "inspect_verification"

    def create(
        self, cfg: VerificationOperationConfig, **dependencies: Any
    ) -> InspectVerificationOperation:
        return InspectVerificationOperation(dependencies["service"])


class CancelVerificationFactory(
    BaseFactory[VerificationOperationConfig, CancelVerificationOperation]
):
    def accepts(self, cfg: VerificationOperationConfig, element_type: str) -> bool:
        return element_type == "cancel_verification"

    def create(
        self, cfg: VerificationOperationConfig, **dependencies: Any
    ) -> CancelVerificationOperation:
        return CancelVerificationOperation(dependencies["service"])


class VerificationConnectionSpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = "verification_service"
    name = "Verification service"
    description = "Scoped workflow access to verification plans, without evidence authority"
    config_schema = VerificationConnection
    factory_cls = VerificationConnectionFactory


class RequestVerificationSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "request_verification"
    name = "Request verification"
    description = "Admit an exact candidate and immutable check requirements for this call"
    config_schema = VerificationOperationConfig
    factory_cls = RequestVerificationFactory
    input_schema = RequestVerification
    result_schema = VerificationView


class InspectVerificationSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "inspect_verification"
    name = "Inspect verification"
    description = "Read authoritative check evidence and candidate acceptance"
    config_schema = VerificationOperationConfig
    factory_cls = InspectVerificationFactory
    input_schema = VerificationHandle
    result_schema = VerificationView


class CancelVerificationSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "cancel_verification"
    name = "Cancel verification"
    description = "Cancel an incomplete verification plan without erasing evidence"
    config_schema = VerificationOperationConfig
    factory_cls = CancelVerificationFactory
    input_schema = VerificationHandle
    result_schema = VerificationView


class StartCheckFactory(BaseFactory[VerificationOperationConfig, StartCheckOperation]):
    def accepts(self, cfg: VerificationOperationConfig, element_type: str) -> bool:
        return element_type == "start_verification_check"

    def create(self, cfg: VerificationOperationConfig, **dependencies: Any) -> StartCheckOperation:
        return StartCheckOperation(dependencies["service"])


class RefreshCheckFactory(BaseFactory[VerificationOperationConfig, RefreshCheckOperation]):
    def accepts(self, cfg: VerificationOperationConfig, element_type: str) -> bool:
        return element_type == "refresh_verification_check"

    def create(
        self, cfg: VerificationOperationConfig, **dependencies: Any
    ) -> RefreshCheckOperation:
        return RefreshCheckOperation(dependencies["service"])


class StartCheckSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "start_verification_check"
    name = "Start verification check"
    description = "Reserve and submit one trusted check; ambiguous outcomes require reconciliation"
    config_schema = VerificationOperationConfig
    factory_cls = StartCheckFactory
    input_schema = StartCheckRun
    result_schema = CheckRun


class RefreshCheckSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "refresh_verification_check"
    name = "Refresh verification check"
    description = "Reconcile a trusted check and record its exact-candidate evidence"
    config_schema = VerificationOperationConfig
    factory_cls = RefreshCheckFactory
    input_schema = CheckRunHandle
    result_schema = CheckRun


ELEMENT_SPECIFICATIONS = (
    VerificationConnectionSpec,
    RequestVerificationSpec,
    InspectVerificationSpec,
    CancelVerificationSpec,
    StartCheckSpec,
    RefreshCheckSpec,
)
