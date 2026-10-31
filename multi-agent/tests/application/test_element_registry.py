"""Catalog composition permits repeated identity, while conflicting implementations fail."""

import pytest
from mas.core.enums import ResourceCategory
from support.elements import EchoSpec


class ConflictingEchoSpec(EchoSpec):
    description = "Another implementation claiming the same catalog identity"


def test_composing_the_same_registered_class_is_idempotent(application):
    application.elements.register_spec_class(EchoSpec)
    assert application.elements.get_spec(ResourceCategory.NODE, EchoSpec.type_key) is EchoSpec


def test_distinct_implementations_cannot_claim_one_catalog_identity(application):
    with pytest.raises(ValueError, match="already registered"):
        application.elements.register_spec_class(ConflictingEchoSpec)
    assert application.elements.get_spec(ResourceCategory.NODE, EchoSpec.type_key) is EchoSpec
