"""Diagnostic content omits declared credentials while preserving typed models and identifiers."""

from pydantic import BaseModel
from support.secrets import SecretToolConfig, SecretToolSpec

from flareward.elements.cards.default import DefaultCardBuilder
from flareward.elements.catalog.card_service import ElementCardService
from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.configuration.meta import ElementConfigMeta
from flareward.elements.domain.cards import Skill
from flareward.elements.validation import (
    BaseElementValidator,
    ValidationCode,
    ValidationContext,
    ValidationSeverity,
)
from flareward.elements.validation_services.service import ElementValidationService
from flareward.resources.domain.categories import ResourceCategory


class Metadata(BaseModel):
    value: str


class ReportValidator(BaseElementValidator):
    def validate(self, config, context):
        return self._build_report(
            [
                self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    "Provider failed: " + config.api_key,
                    field="api_key",
                )
            ]
        )


class ReportCard(DefaultCardBuilder):
    def build(self, input):
        return (
            super()
            .build(input)
            .model_copy(
                update={
                    "skills": [
                        Skill(
                            name="Probe",
                            description=input.config.api_key,
                            echoed=input.config.api_key,
                        )
                    ],
                    "configuration": {"nested": [input.config.api_key]},
                    "metadata": Metadata(value=input.config.api_key),
                }
            )
        )


class ReportSpec(SecretToolSpec):
    validator_cls = ReportValidator
    card_builder_cls = ReportCard


def inspected():
    registry = ElementRegistry()
    registry.register_spec_class(ReportSpec)
    meta = ElementConfigMeta(
        rid="private-token",
        category=ResourceCategory.TOOL,
        type_key=ReportSpec.type_key,
        name="Resource",
        config=SecretToolConfig(api_key="private-token"),
    )
    return registry, meta


def test_validation_redacts_sdk_message_content_and_preserves_codes_and_scope():
    registry, meta = inspected()
    result = ElementValidationService(registry).validate(meta, ValidationContext())
    assert result.element_rid == "private-token" and result.element_type == ReportSpec.type_key
    assert result.messages[0].message == "Provider failed: [redacted]"
    assert result.messages[0].code == ValidationCode.ENDPOINT_UNREACHABLE.value
    assert (
        result.messages[0].field == "api_key"
        and result.messages[0].severity == ValidationSeverity.ERROR
    )
    assert meta.config.api_key == "private-token"


def test_cards_redact_nested_values_and_model_extras_without_changing_model_types():
    registry, meta = inspected()
    card = ElementCardService(registry).build_single_card(meta)
    assert card.uid == "private-token" and card.category is ResourceCategory.TOOL
    assert card.skills[0].description == card.skills[0].model_extra["echoed"] == "[redacted]"
    assert card.configuration == {"nested": ["[redacted]"]}
    assert isinstance(card.metadata, Metadata) and card.metadata.value == "[redacted]"
    assert meta.config.api_key == "private-token"
