"""Metadata validation shared by native and drain-compatible authoring services."""

import re
from collections.abc import Mapping

from flareward.programs.templates.exceptions import InvalidMetadataKeysError

_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


def validate_metadata_keys(metadata: Mapping[str, object]) -> None:
    invalid = [key for key in metadata if not _KEY.fullmatch(key)]
    if invalid:
        raise InvalidMetadataKeysError(invalid)
