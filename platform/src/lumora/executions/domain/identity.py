"""Canonical business request identity, independent of execution progress."""

import hashlib
import json

from lumora.executions.domain.models import ExecutionRecord


def request_digest(record: ExecutionRecord) -> str:
    data = {
        "owner": {"type": record.owner.type, "id": record.owner.id},
        "program": record.program.model_dump(mode="json"),
        "body_path": record.body_path,
        "content_digest": record.content_digest,
        "workflow_access_approval": record.workflow_access_approval.model_dump(mode="json")
        if record.workflow_access_approval
        else None,
        "work_limits": record.work_limits.model_dump(mode="json") if record.work_limits else None,
        "admitted_profiles": record.admitted_profiles.model_dump(mode="json")
        if record.admitted_profiles
        else None,
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
