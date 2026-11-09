from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the SSH Exec tool."""

    TYPE = "ssh_exec"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="SSH Exec",
    description="Execute a shell command on a remote VM",
    tags=["tool", "ssh", "exec", "remote", "execution"],
)
