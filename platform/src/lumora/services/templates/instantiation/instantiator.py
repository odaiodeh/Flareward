"""
Template instantiator for merging user input into BlueprintDraft.

SOLID Principles:
- SRP: Each method has one responsibility
- OCP: Extensible without modification
- DIP: Depends on abstractions (Template, BlueprintDraft)
"""

from typing import Any, Dict, List, Optional

from lumora.programs.templates.models.blueprint import BlueprintDraft, BlueprintResource
from lumora.services.templates.errors import MergeError, MergeErrorType, MergeFieldError
from lumora.services.templates.instantiation.models import InstantiationResult
from lumora.services.templates.models.template import (
    PlaceholderMeta,
    PlaceholderPointer,
    Template,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Instantiator
# ─────────────────────────────────────────────────────────────────────────────
class TemplateInstantiator:
    """
    Merges user input into template draft to produce BlueprintDraft.

    The template draft is already valid - this replaces placeholder
    default values with actual user input.
    """

    def instantiate(
        self,
        template: Template,
        user_input: Dict[str, Any],
    ) -> InstantiationResult:
        """
        Instantiate template with user input.

        Returns InstantiationResult containing:
        - blueprint: The merged BlueprintDraft
        - template_id: Source template ID
        - filled_fields: List of fields that were filled

        Raises MergeError if required fields missing.
        """
        draft = self._copy_draft(template.draft)
        errors = self._merge_placeholders(draft, template.placeholders, user_input)

        if errors:
            raise MergeError(
                message=f"Merge failed with {len(errors)} error(s)",
                errors=errors,
            )

        filled_fields = self._collect_filled_fields(template.placeholders, user_input)

        return InstantiationResult(
            blueprint=draft,
            template_id=template.template_id,
            filled_fields=filled_fields,
        )

    # ─────────────────────────────────────────────────────────────────────
    #  Merge Operations
    # ─────────────────────────────────────────────────────────────────────
    def _merge_placeholders(
        self,
        draft: BlueprintDraft,
        placeholders: PlaceholderMeta,
        user_input: Dict[str, Any],
    ) -> List[MergeFieldError]:
        """Merge all placeholder values into draft. Returns list of errors."""
        errors: List[MergeFieldError] = []

        for cat_placeholder in placeholders.categories:
            category = cat_placeholder.category
            cat_input = user_input.get(category.value, {})
            resources = getattr(draft, category.value, [])

            for res_placeholder in cat_placeholder.resources:
                rid = res_placeholder.rid
                resource = self._find_resource(resources, rid)

                if resource is None:
                    errors.append(
                        MergeFieldError(
                            category=category.value,
                            rid=rid,
                            error_type=MergeErrorType.RESOURCE_NOT_FOUND,
                            message=f"Resource '{rid}' not found in draft",
                        )
                    )
                    continue

                res_input = cat_input.get(rid, {})
                errors.extend(
                    self._merge_resource_fields(
                        resource=resource,
                        placeholders=res_placeholder.placeholders,
                        user_input=res_input,
                        category=category.value,
                        rid=rid,
                    )
                )

        return errors

    def _merge_resource_fields(
        self,
        resource: BlueprintResource,
        placeholders: List[PlaceholderPointer],
        user_input: Dict[str, Any],
        category: str,
        rid: str,
    ) -> List[MergeFieldError]:
        """Merge fields for a single resource. Returns list of errors."""
        errors: List[MergeFieldError] = []

        for placeholder in placeholders:
            field_name = self._field_name(placeholder.field_path)

            if field_name in user_input:
                self._set_field(resource, placeholder.field_path, user_input[field_name])
            elif placeholder.required:
                errors.append(
                    MergeFieldError(
                        category=category,
                        rid=rid,
                        field=placeholder.field_path,
                        error_type=MergeErrorType.FIELD_REQUIRED,
                        message=f"Required field '{placeholder.field_path}' not provided",
                    )
                )

        return errors

    def _set_field(
        self,
        resource: BlueprintResource,
        field_path: str,
        value: Any,
    ) -> bool:
        """Set field value in resource config. Returns True if successful."""
        if resource.config is None:
            return False

        parts = field_path.split(".")
        target = resource.config

        # Navigate to parent for nested paths
        for part in parts[:-1]:
            if not hasattr(target, part):
                return False
            target = getattr(target, part)

        # Set final value
        final_field = parts[-1]
        if hasattr(target, final_field):
            setattr(target, final_field, value)
            return True

        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────
    def _copy_draft(self, draft: BlueprintDraft) -> BlueprintDraft:
        """Create deep copy of blueprint draft."""
        return BlueprintDraft.model_validate(draft.model_dump(mode="python"))

    def _find_resource(
        self,
        resources: List[BlueprintResource],
        rid: str,
    ) -> Optional[BlueprintResource]:
        """Find resource by rid."""
        for resource in resources:
            if resource.rid.ref == rid:
                return resource
        return None

    @staticmethod
    def _field_name(field_path: str) -> str:
        """Extract field name from path (e.g., 'lumora.bootstrap.settings.api_key' → 'api_key')."""
        return field_path.split(".")[-1]

    # ─────────────────────────────────────────────────────────────────────
    #  Tracking
    # ─────────────────────────────────────────────────────────────────────
    def _collect_filled_fields(
        self,
        placeholders: PlaceholderMeta,
        user_input: Dict[str, Any],
    ) -> List[str]:
        """Collect list of fields that were filled by user."""
        filled: List[str] = []

        for cat_placeholder in placeholders.categories:
            category = cat_placeholder.category.value
            cat_input = user_input.get(category, {})

            for res_placeholder in cat_placeholder.resources:
                rid = res_placeholder.rid
                res_input = cat_input.get(rid, {})

                for placeholder in res_placeholder.placeholders:
                    if self._field_name(placeholder.field_path) in res_input:
                        filled.append(f"{category}.{rid}.{placeholder.field_path}")

        return filled
