"""Bundle integrity survives equivalent JSON numbers, never changed configuration."""

import pytest
from pydantic import ValidationError

from lumora.resources.domain.bundles import (
    BundleEntry,
    ElementBundle,
    ResourceDefinition,
    ResourceKey,
)
from lumora.resources.domain.categories import ResourceCategory


def numeric_bundle(value):
    key = ResourceKey(category=ResourceCategory.OPERATION, rid="numeric")
    return ElementBundle(
        root=key,
        entries=(
            BundleEntry(
                resource=ResourceDefinition(
                    key=key, type_key="numeric", config={"nested": [{"number": value}]}
                )
            ),
        ),
    )


@pytest.mark.parametrize("number", [120.0, -0.0, 1e20, -2.0])
def test_equivalent_json_integer_preserves_integrity_without_retyping_config(number):
    original = numeric_bundle(number)
    assert isinstance(original.entries[0].resource.config["nested"][0]["number"], float)
    wire = original.model_dump(mode="json")
    wire["entries"][0]["resource"]["config"]["nested"][0]["number"] = int(number)
    restored = ElementBundle.model_validate(wire)
    assert restored.content_digest == original.content_digest
    assert numeric_bundle(int(number)).content_digest == original.content_digest


@pytest.mark.parametrize(
    "original,changed", [(120.0, 121), (0.1, 0.2), (1, "1"), (2**53 + 1, 2**53)]
)
def test_changed_or_rounded_values_cannot_reuse_a_digest(original, changed):
    wire = numeric_bundle(original).model_dump(mode="json")
    wire["entries"][0]["resource"]["config"]["nested"][0]["number"] = changed
    with pytest.raises(ValidationError, match="digest does not match"):
        ElementBundle.model_validate(wire)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_cannot_identify_a_bundle(number):
    with pytest.raises(ValidationError):
        numeric_bundle(number)


def test_old_number_identity_format_is_not_silently_reinterpreted():
    wire = numeric_bundle(120).model_dump(mode="json")
    wire["schema_version"] = 1
    with pytest.raises(ValidationError, match="schema_version"):
        ElementBundle.model_validate(wire)
