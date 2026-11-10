from enum import StrEnum


class ConnectionType(StrEnum):
    DEPENDENCY = "dependency"
    BRANCH = "branch"


class OrphanFixType(StrEnum):
    REMOVE_ORPHAN = "remove_orphan"
    CONNECT_TO_WORKFLOW = "connect_to_workflow"
