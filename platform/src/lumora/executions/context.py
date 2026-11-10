"""Receiver-local mutable context reference, never part of a portable payload."""

from lumora.executions.domain.context import ExecutionContext
from lumora.services.identity.domain import Identity


class ExecutionContextHolder:
    """Mutable reference to an immutable ExecutionContext.

    Created at build time (uninitialised).  Filled at execution time
    (real values).  Elements receive a closure over this object — they
    read current values when they need them.

    Fail-fast: accessing ``context``, ``scope``, or ``identity_id`` before
    the holder is filled raises ``RuntimeError`` instead of returning
    silent defaults.
    """

    __slots__ = ("_ctx",)

    def __init__(self) -> None:
        self._ctx: ExecutionContext | None = None

    @property
    def context(self) -> ExecutionContext:
        if self._ctx is None:
            raise RuntimeError(
                "ExecutionContext not initialised — "
                "ensure lifecycle.begin() runs before element execution"
            )
        return self._ctx

    @context.setter
    def context(self, value: ExecutionContext) -> None:
        self._ctx = value

    @property
    def scope(self) -> str:
        return self.context.scope

    @property
    def identity_id(self) -> str:
        return self.context.identity_id

    @property
    def identity(self) -> Identity:
        return self.context.identity
