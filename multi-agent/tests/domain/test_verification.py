"""Evidence subjects bind exact portable data without a Git/blob union."""

import pytest
from mas.domain.verification import VerificationSubject
from pydantic import ValidationError


def test_subject_identity_is_order_independent_and_kind_specific():
    first = VerificationSubject(kind="release@1", identity={"version": 1, "name": "product"})
    reordered = VerificationSubject(kind="release@1", identity={"name": "product", "version": 1})
    assert first.fingerprint == reordered.fingerprint
    assert (
        first.fingerprint
        != VerificationSubject(kind="release@2", identity=first.identity).fingerprint
    )
    assert (
        first.fingerprint
        != VerificationSubject(
            kind="release@1", identity={"version": 2, "name": "product"}
        ).fingerprint
    )


@pytest.mark.parametrize(
    "kind,identity",
    [
        ("git-revision@1", {"repository": "source", "commit": "a" * 40}),
        ("build-image@1", {"image": "product", "digest": "sha256:" + "a" * 64}),
        ("document@1", {"id": "requirements", "revision": 3}),
    ],
)
def test_check_subjects_support_independent_typed_identity_protocols(kind, identity):
    subject = VerificationSubject(kind=kind, identity=identity)
    assert len(subject.fingerprint) == 64


@pytest.mark.parametrize(
    "identity", [{}, {"bad": float("nan")}, {"bad": float("inf")}, {"text": "x" * 65_536}]
)
def test_subjects_reject_empty_nonportable_and_oversized_data(identity):
    with pytest.raises(ValidationError):
        VerificationSubject(kind="document@1", identity=identity)
