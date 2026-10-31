"""Canonical business request identity, independent of execution progress."""

import hashlib
import json

from mas.execution.models import ExecutionRecord


def request_digest(record: ExecutionRecord) -> str:
    data = {
        "owner": {"type": record.owner.type, "id": record.owner.id},
        "program": record.program.model_dump(mode="json"),
        "inputs": record.inputs,
        "session_id": record.session_id,
        "parent_execution_id": record.parent_execution_id,
        "engine_handle": record.context.engine_handle,
        "context": {
            "owner": {"type": record.context.identity.type, "id": record.context.identity.id},
            "session_id": record.context.session_id,
            "execution_id": record.context.execution_id,
            "root_execution_id": record.context.root_execution_id,
            "parent_execution_id": record.context.parent_execution_id,
            "ancestor_execution_ids": record.context.ancestor_execution_ids,
            "scope": record.context.scope,
            "engine_name": record.context.engine_name,
            "tags": record.context.tags,
        },
    }
    if record.location:
        data["location"] = record.location
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()
