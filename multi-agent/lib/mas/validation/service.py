"""
validation/service.py

ElementValidationService - orchestrates validation.

Responsibilities:
- Look up validators from ElementRegistry
- Call validators with proper context
- Build ElementValidationResult from ValidatorReport + metadata
- Accumulate results for ordered validation

Does NOT:
- Know about Resources or Blueprints
- Fetch data from database
- Resolve references
"""

import asyncio

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.validation import (
    ElementValidationResult,
    ValidationCode,
    ValidationContext,
    ValidationMessage,
    ValidationSeverity,
    ValidatorReport,
)
from mas.core.async_work import await_owned
from mas.core.element_meta import ElementConfigMeta
from mas.core.secrets import redact_configuration_values


class ElementValidationService:
    """
    Pure validation service.

    Receives configs, returns results.
    Only dependency is ElementRegistry (to find validators).
    Native async validation and retained synchronous callers share report construction.

    Validators return ValidatorReport (what they found).
    Service builds ElementValidationResult (report + metadata).
    """

    def __init__(self, element_registry: ElementRegistry):
        self._registry = element_registry

    def validate(
        self,
        config_meta: ElementConfigMeta,
        context: ValidationContext,
    ) -> ElementValidationResult:
        """
        Validate a single config.

        Looks up the validator from ElementRegistry and calls it.
        Builds ElementValidationResult from ValidatorReport + metadata.
        If no validator is defined, returns success with INFO message.

        If ``config_meta.validation_override_error`` is set, the real
        validator is skipped entirely and this fails immediately with that
        message — e.g. a built-in resource whose caller has no per-identity
        overlay for a required secret field. This keeps that veto generic
        (a plain flag on the metadata) rather than importing any
        Resources/built-in-specific logic here.
        """
        result = self._preflight(config_meta)
        if result is not None:
            return result
        validator = self._registry.get_spec(
            config_meta.category, config_meta.type_key
        ).validator_cls()
        return self._build_result(config_meta, validator.validate(config_meta.config, context))

    async def validate_async(
        self, config_meta: ElementConfigMeta, context: ValidationContext
    ) -> ElementValidationResult:
        result = self._preflight(config_meta)
        if result is not None:
            return result
        validator = self._registry.get_spec(
            config_meta.category, config_meta.type_key
        ).validator_cls()
        operation = asyncio.create_task(validator.validate_async(config_meta.config, context))
        report = await await_owned(operation, on_cancel=operation.cancel)
        return self._build_result(config_meta, report)

    async def validate_ordered_async(
        self, configs: list[ElementConfigMeta], base_context: ValidationContext
    ) -> dict[str, ElementValidationResult]:
        results = {}
        for meta in configs:
            results[meta.rid] = await self.validate_async(
                meta, base_context.with_dependency_results(results)
            )
        return results

    def _preflight(self, config_meta: ElementConfigMeta) -> ElementValidationResult | None:
        if config_meta.validation_override_error:
            return ElementValidationResult(
                is_valid=False,
                element_rid=config_meta.rid,
                element_type=config_meta.type_key,
                name=config_meta.name,
                messages=[
                    ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.MISSING_REQUIRED_FIELD.value,
                        message=config_meta.validation_override_error,
                    )
                ],
            )

        if (
            self._registry.get_spec(config_meta.category, config_meta.type_key).validator_cls
            is None
        ):
            return ElementValidationResult(
                is_valid=True,
                element_rid=config_meta.rid,
                element_type=config_meta.type_key,
                name=config_meta.name,
                messages=[
                    ValidationMessage(
                        severity=ValidationSeverity.INFO,
                        code=ValidationCode.NO_VALIDATOR.value,
                        message="No validator defined; schema validation passed",
                    )
                ],
            )

        return None

    def _build_result(
        self,
        config_meta: ElementConfigMeta,
        report: ValidatorReport,
    ) -> ElementValidationResult:
        """
        Build ElementValidationResult from ValidatorReport + metadata.

        The service knows the element metadata (rid, type, name).
        The validator only knows what it found (messages, checked deps).
        """
        texts = redact_configuration_values(
            config_meta.config, [message.message for message in report.messages]
        )
        return ElementValidationResult(
            is_valid=report.is_valid,
            element_rid=config_meta.rid,
            element_type=config_meta.type_key,
            name=config_meta.name,
            messages=[
                message.model_copy(update={"message": text})
                for message, text in zip(report.messages, texts, strict=True)
            ],
            dependency_results=report.checked_dependencies,
        )

    def validate_ordered(
        self,
        configs: list[ElementConfigMeta],
        base_context: ValidationContext,
    ) -> dict[str, ElementValidationResult]:
        """
        Validate multiple configs in the given order.

        Caller is responsible for providing configs in dependency order
        (dependencies before dependents).

        Results accumulate in context so later validators can see
        earlier results.
        """
        results: dict[str, ElementValidationResult] = {}

        for config_meta in configs:
            context = base_context.with_dependency_results(results)
            result = self.validate(config_meta, context)
            results[config_meta.rid] = result

        return results
