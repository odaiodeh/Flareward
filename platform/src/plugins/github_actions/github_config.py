"""Operator-admitted GitHub workflow behavior and private transport settings."""

import hashlib
import json
import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from lumora.services.verification.check_ports import CheckRunnerPolicy
from plugins.git.domain.repositories import GitCommitId, RepositoryId


class GitHubCheckConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    policy: CheckRunnerPolicy
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=160)
    source_repository: RepositoryId
    workflow_id: int = Field(gt=0)
    workflow_ref: str = Field(min_length=1, max_length=256)
    workflow_commit: GitCommitId
    token: SecretStr = Field(min_length=1, repr=False)
    timeout_seconds: float = Field(default=20, ge=1, le=120, allow_inf_nan=False)
    reconciliation_pages: int = Field(default=10, ge=1, le=10)
    report_names: tuple[str, ...] = Field(default=(), max_length=16)
    report_max_bytes: int = Field(default=16_777_216, ge=1, le=67_108_864)
    archive_hosts: frozenset[str] = Field(default=frozenset(), max_length=32)

    @model_validator(mode="after")
    def valid_binding(self) -> Self:
        if self.policy.subject_kind != "git-revision@1":
            raise ValueError("GitHub checks require the Git revision subject contract")
        if len(set(self.report_names)) != len(self.report_names) or any(
            not name or len(name) > 128 for name in self.report_names
        ):
            raise ValueError("GitHub report names must be unique and bounded")
        if self.report_names and not self.archive_hosts:
            raise ValueError("GitHub reports require explicit archive download hosts")
        if any(
            not re.fullmatch(r"(?:\*\.)?[a-z0-9][a-z0-9.-]*[a-z0-9]", host)
            or ".." in host
            or "." not in host
            or not re.search(r"[a-z]", host)
            for host in self.archive_hosts
        ):
            raise ValueError("GitHub archive hosts must be lowercase DNS names or suffix patterns")
        if (
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]*", self.workflow_ref)
            or ".." in self.workflow_ref
            or self.workflow_ref.endswith(("/", ".lock"))
        ):
            raise ValueError("GitHub check workflow requires a safe branch or tag reference")
        return self

    @property
    def digest(self) -> str:
        # Credential rotation does not change the admitted workflow's behavior.
        value = self.model_dump(
            mode="json", exclude={"token", "timeout_seconds", "reconciliation_pages"}
        )
        value["policy"]["policies"] = sorted(value["policy"]["policies"])
        value["archive_hosts"] = sorted(value["archive_hosts"])
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
