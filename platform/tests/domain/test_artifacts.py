"""Content metadata cannot inject response headers or require non-ASCII MIME encoding."""

import base64

import pytest
from pydantic import ValidationError
from support.artifacts import inline_artifact, inline_content, publication

from flareward.services.artifacts.domain.models import (
    InlineArtifact,
    InlineContent,
    PublishArtifact,
)


@pytest.mark.parametrize(
    "media_type", ["text/\u03bb", "text/html\r\nSet-Cookie: private", "text/*"]
)
def test_artifact_media_types_are_concrete_ascii_header_values(media_type):
    with pytest.raises(ValidationError):
        PublishArtifact.model_validate({**publication().model_dump(), "media_type": media_type})


@pytest.mark.parametrize("data", ["not base64", base64.b64encode(b"changed").decode()])
def test_inline_artifact_transport_rejects_malformed_or_changed_content(data):
    artifact = inline_artifact()
    with pytest.raises(ValidationError):
        InlineArtifact.model_validate({**artifact.model_dump(), "data": data})


def test_inline_artifact_transport_round_trips_without_raw_data_in_repr():
    artifact = inline_artifact()
    assert (
        InlineArtifact.model_validate_json(artifact.model_dump_json()).decoded()
        == artifact.decoded()
    )
    assert artifact.data not in repr(artifact)


@pytest.mark.parametrize("data", ["not base64", base64.b64encode(b"changed").decode()])
def test_unpublished_content_also_requires_its_exact_bounded_identity(data):
    content = inline_content()
    with pytest.raises(ValidationError):
        InlineContent.model_validate({**content.model_dump(), "data": data})
    assert content.data not in repr(content)
