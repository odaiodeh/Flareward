from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterator, Set, Tuple

from flareward.programs.graph.state.graph_state import GraphState


class StateView:
    """
    Read/write-restricted proxy for an existing GraphState.

    • Does NOT inherit from GraphState / BaseModel → no Pydantic internals.
    • Delegates every attribute / method call to the backing GraphState
      after enforcing channel permissions.
    """

    __slots__ = ("_b", "_r", "_w")  # lean proxy

    def __init__(self, backing: GraphState, *, reads: Set[str], writes: Set[str]) -> None:
        object.__setattr__(self, "_b", backing)
        object.__setattr__(self, "_r", reads)
        object.__setattr__(self, "_w", writes)

    # ---------- attribute delegation ----------
    def __getattr__(self, item: str) -> Any:
        """
        • If `item` is a channel name, enforce read-permission and
          return a DEEP-COPY when the channel is read-only.
        • Otherwise delegate (model_dump, keys, etc.).
        """
        # Is this attribute one of GraphState’s declared fields?
        if item in self._b.__class__.model_fields:  # declared channel
            self._ensure_readable(item)
            value = getattr(self._b, item)
            return value if item in self._w else deepcopy(value)
        # Fallback: hand over to GraphState
        return getattr(self._b, item)

    def __setattr__(self, key: str, value: Any) -> None:
        # internal slot?
        if key in self.__slots__:
            object.__setattr__(self, key, value)
            return
        # attempt to write a channel attribute (e.g. state.messages = …)
        if key not in self._w:
            raise KeyError(f"Write to undeclared channel {key!r}")
        setattr(self._b, key, value)

    # ---------- dict-like API ----------
    def __getitem__(self, key: str) -> Any:
        self._ensure_readable(key)
        value = self._b[key]
        return value if key in self._w else deepcopy(value)

    def get(self, key: str, default=None) -> Any:
        self._ensure_readable(key)
        val = self._b.get(key, default)
        return val if key in self._w else deepcopy(val)

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self._w:
            raise KeyError(f"Write to undeclared channel {key!r}")
        self._b[key] = value

    # ---------- helpers ----------
    def _ensure_readable(self, key: str) -> None:
        if key not in self._r and key not in self._w:
            raise KeyError(f"Read from undeclared channel {key!r}")

    # expose common iterators so LangGraph / callers are happy
    def keys(self) -> Iterator[str]:
        return self._b.keys()

    def items(self) -> Iterator[Tuple[str, Any]]:
        return self._b.items()

    def dict(self, *a, **kw):
        return self._b.dict(*a, **kw)

    model_dump = dict  # alias for Pydantic helpers

    @property
    def backing_state(self) -> GraphState:
        """
        Return the original GraphState this view is wrapping.
        """
        return self._b

    # nice repr
    def __repr__(self) -> str:
        return f"StateView(reads={self._r}, writes={self._w}, data={self._b.dict()})"
