"""Installed deterministic validators and cards exercise actual caller and dependency context."""

import hashlib

from pydantic import Field

from flareward.elements.cards.default import DefaultCardBuilder
from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.domain.cards import Capability
from flareward.elements.hints import ReadOnlyHint
from flareward.elements.validation import (
    BaseElementValidator,
    ValidationCode,
    ValidatorReport,
)
from plugins.testing.elements.mock_agent.spec.spec import MockAgentNodeElementSpec
from support.blueprints import OverlayMockConfig, OverlayMockSpec


class InspectedModelConfig(OverlayMockConfig):
    label: str = Field(default="Shared", json_schema_extra=ReadOnlyHint(read_only=False).to_hints())
    expected_digest: str = hashlib.sha256(b"caller-model-private").hexdigest()
    expected_owner: str = "workspace"
    expected_human: str = "human"
    fail: bool = False
    report_failure: bool = False


class ModelValidator(BaseElementValidator):
    def validate(self, config, context):
        if config.fail:
            raise RuntimeError("Provider failed with " + config.api_key)
        if config.report_failure:
            return self._build_report(
                [
                    self._error(
                        ValidationCode.ENDPOINT_UNREACHABLE.value,
                        "Provider failed with " + config.api_key,
                    )
                ]
            )
        assert context.user_id == config.expected_owner
        assert context.credential_lookup_user_id() == config.expected_human
        assert context.auth_service is not None
        credential = context.auth_service.get_credential(
            config.expected_human, "inspection", "api_key"
        )
        assert credential is not None and credential.access_token == "probe-server-private"
        valid = hashlib.sha256(config.api_key.encode()).hexdigest() == config.expected_digest
        return ValidatorReport(
            messages=[]
            if valid
            else [self._error(ValidationCode.INVALID_CREDENTIALS.value, "Credential mismatch")]
        )


class ModelCard(DefaultCardBuilder):
    def build(self, input):
        return (
            super()
            .build(input)
            .model_copy(
                update={
                    "capabilities": [Capability(name="model_label", description=input.config.label)]
                }
            )
        )


class InspectedModelSpec(OverlayMockSpec):
    config_schema = InspectedModelConfig
    validator_cls = ModelValidator
    card_builder_cls = ModelCard


class AgentValidator(BaseElementValidator):
    def validate(self, config, context):
        messages, dependencies = [], {}
        if config.llm is not None:
            self._check_dependency(context, config.llm.ref, "llm", messages, dependencies)
        return self._build_report(messages, dependencies)


class InspectedAgentSpec(MockAgentNodeElementSpec):
    validator_cls = AgentValidator


def inspection_elements():
    elements = ElementRegistry()
    elements.register_spec_class(InspectedModelSpec)
    elements.register_spec_class(InspectedAgentSpec)
    return elements
