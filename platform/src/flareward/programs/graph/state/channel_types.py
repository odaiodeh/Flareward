"""
State channel types for GraphState field merge behavior.

Mirrors LangGraph's channel architecture (last_value.py, binop.py):
  - LastValueChannel  → LangGraph's LastValue
  - BinOpChannel      → LangGraph's BinaryOperatorAggregate

Key difference from LangGraph: our nodes return the FULL GraphState,
not just a dict of their writes. So each channel type implements
extract_write() to infer what the node actually changed, before
applying update().

Pipeline per parallel superstep (mirrors apply_writes in _algo.py):
  1. channel.extract_write(original, result)  → the node's "write"
  2. collect all writes per field             → pending_writes_by_channel
  3. channel.update(base, [write_A, write_B]) → reconciled value
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, List, get_type_hints

_MISSING = object()  # sentinel — this field was not written by the node


class BaseStateChannel(ABC):
    """
    Abstract channel. Every GraphState field maps to one channel instance,
    determined by its Annotated metadata (or the absence of it).
    """

    @abstractmethod
    def extract_write(self, original: Any, modified: Any) -> Any:
        """
        Infer what a node 'wrote' to this field.

        Args:
            original: field value BEFORE the node ran (pre-execution snapshot)
            modified: field value AFTER the node ran (from the result state)

        Returns:
            The write value to feed into update().
            Returns _MISSING sentinel when the node did not change this field.
        """

    @abstractmethod
    def update(self, base: Any, writes: List[Any]) -> Any:
        """
        Reconcile all parallel writes against the base (pre-execution) value.

        Mirrors LangGraph's BinaryOperatorAggregate.update(values):
            for value in values:
                self.value = self.operator(self.value, value)

        Args:
            base:   field value before any parallel node ran
            writes: writes from each parallel node (MISSING-filtered)

        Returns:
            The fully reconciled field value.
        """


class LastValueChannel(BaseStateChannel):
    """
    Scalar field — last write wins.

    Mirrors LangGraph's LastValue channel.
    Used for fields like: user_prompt, output, target_branch.

    In a parallel superstep only one node should write a scalar.
    If two nodes do write different values we take the last (safe degradation).
    """

    def extract_write(self, original: Any, modified: Any) -> Any:
        if original == modified:
            return _MISSING
        return modified

    def update(self, base: Any, writes: List[Any]) -> Any:
        if not writes:
            return base
        return writes[-1]  # last write wins — matches LangGraph LastValue


class BinOpChannel(BaseStateChannel):
    """
    Reducer field — applies a binary operator to accumulate writes.

    Mirrors LangGraph's BinaryOperatorAggregate.

    Used for Annotated[T, reducer_fn] fields:
        messages       → append_chat_messages
        inter_packets  → append_iem_packets
        nodes_output   → merge_string_dicts
        task_threads   → merge_task_threads
        threads        → merge_threads
        workspaces     → merge_workspaces

    extract_write uses type-aware inference so operators always receive
    the right shape of data:

      Lists — pure append (original is a prefix of modified):
          extract only the new tail items (the increment).
          e.g. [m1,m2,m3] → original=[m1,m2] → write=[m3]
          Operator sees small deltas → no duplication on parallel merge.

      Lists — in-place mutation (same length or items changed, e.g. ack_by):
          extract the full modified list.
          Operator must reconcile same-ID items (union ack_by).

      Dicts:
          extract only new or changed keys (the increment).

      Other (scalars used as BinOp, rare):
          extract the full new value.
    """

    def __init__(self, operator: Callable[[Any, Any], Any]) -> None:
        self.operator = operator

    def extract_write(self, original: Any, modified: Any) -> Any:
        if original == modified:
            return _MISSING

        if isinstance(original, list) and isinstance(modified, list):
            if len(modified) > len(original) and modified[: len(original)] == original:
                # Pure append: return only the new tail
                return modified[len(original) :]
            # In-place mutation: return full list; operator handles reconciliation
            return modified

        if isinstance(original, dict) and isinstance(modified, dict):
            return _dict_increment(original, modified)

        return modified

    def update(self, base: Any, writes: List[Any]) -> Any:
        """
        Reduce all writes sequentially, starting from base.

        Exactly mirrors BinaryOperatorAggregate.update():
            for value in values:
                self.value = self.operator(self.value, value)
        """
        result = base
        for write in writes:
            result = self.operator(result, write)
        return result


# ------------------------------------------------------------------ #
#  Registry builder
# ------------------------------------------------------------------ #


def build_channel_registry(state_cls: type) -> dict[str, BaseStateChannel]:
    """
    Inspect GraphState field annotations and assign each field a channel.

    Rules (same as LangGraph):
        Annotated[T, reducer_fn]  →  BinOpChannel(reducer_fn)
        plain T                   →  LastValueChannel()

    Called once at GraphTraversal construction time.
    """

    hints = get_type_hints(state_cls, include_extras=True)
    registry: dict[str, BaseStateChannel] = {}

    for field_name in state_cls.model_fields:
        hint = hints.get(field_name)
        channel: BaseStateChannel = LastValueChannel()  # default
        if hint and hasattr(hint, "__metadata__"):
            for meta in hint.__metadata__:
                if callable(meta):
                    channel = BinOpChannel(meta)
                    break
        registry[field_name] = channel

    return registry


# ------------------------------------------------------------------ #
#  Private helpers
# ------------------------------------------------------------------ #


def _dict_increment(original: dict, modified: dict) -> dict:
    """
    Return only keys that are new or have changed values.
    For dict-valued keys whose values are lists, applies list-increment logic.
    """
    diff: dict = {}
    for k, v in modified.items():
        if k not in original:
            diff[k] = v
        elif v != original[k]:
            if isinstance(original[k], list) and isinstance(v, list):
                # Nested list: prefer increment if pure append
                if len(v) > len(original[k]) and v[: len(original[k])] == original[k]:
                    diff[k] = v[len(original[k]) :]
                else:
                    diff[k] = v
            else:
                diff[k] = v
    return diff
