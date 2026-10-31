"""Pin one coordinator configuration without creating another backend registry."""

import hashlib
import json
from uuid import uuid4

from runengine.adapters.coordination.config import LocalHostConfig, RunHostConfig


def host_location(config: RunHostConfig) -> str:
    if isinstance(config, LocalHostConfig):
        # Even identical Local configuration cannot recover another host's lost work.
        return "runengine:local:" + uuid4().hex
    data = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return "runengine:coordinator:" + hashlib.sha256(data.encode()).hexdigest()
