from collections.abc import Sequence
from itertools import islice
from typing import Any

from lumora.elements.messaging.domain.messages import ChatMessage, Role


def merge_string_dicts(existing: dict[str, str], new_item: Any) -> dict[str, str]:
    """
    Merge strategy for Dict[str, str]:
    - Accepts new_item as dict[str, str]
    - Overwrites or adds keys
    - Returns merged result
    """
    if not isinstance(existing, dict):
        existing = {}
    if isinstance(new_item, dict):
        # filter only str->str keys for safety
        merged = existing.copy()
        for k, v in new_item.items():
            if isinstance(k, str) and isinstance(v, str):
                merged[k] = v
        return merged
    return existing


def _to_chat(msg: Any):
    """Single-pass conversion to ChatMessage (or None)."""
    if isinstance(msg, ChatMessage):
        return msg
    if isinstance(msg, dict) and "role" in msg and "content" in msg:
        return ChatMessage(**msg)
    if isinstance(msg, str):
        return ChatMessage(role=Role.ASSISTANT, content=msg)
    return None


def _same_history(a: Sequence[ChatMessage], b: Sequence[ChatMessage]) -> bool:
    """
    True when *all* messages in `a` equal the messages at the same positions in `b`.
    Works because dataclasses give ChatMessage a value-based __eq__.
    """
    return all(x == y for x, y in zip(a, islice(b, len(a))))


def append_chat_messages(existing: list[ChatMessage] | None, new_item: Any) -> list[ChatMessage]:
    """
    Smart-merge for the `messages` channel.

    • Accepts `ChatMessage`, str, dict, list/tuple[…].
    • **If the node returned the full history**
      (i.e. new list starts with all the old messages in the same order)
      → replace the channel with that list.
    • Otherwise **treat the input as incremental** and simply append.
    • No cross-list de-duplication – duplicates are kept intentionally
      so `[x, y, z] + x` becomes `[x, y, z, x]`.
    """
    existing = existing or []
    # Normalise to a list[ChatMessage]
    raw_list = new_item if isinstance(new_item, (list, tuple)) else [new_item]
    incoming: list[ChatMessage] = [cm for cm in (_to_chat(r) for r in raw_list) if cm is not None]

    if not incoming:
        return existing

    # ── Case A: node returned the *entire* history ──────────────────────────
    # e.g. existing = [x, y, z] • incoming = [x, y, z, x]
    #      → keep incoming as the new canonical history.
    if len(incoming) >= len(existing) and _same_history(existing, incoming):
        return incoming

    # ── Case B: node returned *only the new* messages ───────────────────────
    return existing + incoming


def append_iem_packets(existing: list | None, new_item: list | Any) -> list:
    """
    Merge strategy for IEM packets channel.

    Handles two scenarios, matching how BinOpChannel.extract_write() feeds data:

    Scenario A — pure increment (new packets added by the node):
        new_item = [PacketC]  (unseen ID)
        → appended, insertion order preserved.

    Scenario B — full list with in-place mutations (ack_by changed):
        new_item = [P1(ack_by={"Jira"}), P2(ack_by={})]  (same IDs, different ack_by)
        → same-ID packets are MERGED: ack_by = existing.ack_by | incoming.ack_by
        → acknowledgments written by parallel agents are NEVER lost.

    Called sequentially for each parallel result, exactly like
    BinaryOperatorAggregate.update() in LangGraph:
        result = op(op(base, write_jira), write_conf)

    Example — Jira + Confluence agents run in parallel:
        base       = [P1(ack={}),      P2(ack={})]
        write_jira = [P1(ack={"Jira"}), P2(ack={})]
        write_conf = [P1(ack={}),      P2(ack={"Conf"})]

        after Jira : [P1(ack={"Jira"}),       P2(ack={})]
        after Conf : [P1(ack={"Jira"}),        P2(ack={"Conf"})]  ✓ both acks preserved
    """
    existing = existing or []

    if isinstance(new_item, list):
        incoming = new_item
    else:
        incoming = [new_item] if new_item is not None else []

    valid_incoming = [p for p in incoming if p is not None and hasattr(p, "id")]
    if not valid_incoming:
        return existing

    # Build ordered index: packet_id → packet (preserves insertion order)
    index: dict = {}
    order: list = []
    for p in existing:
        pid = getattr(p, "id", None)
        if pid is not None:
            index[pid] = p
            order.append(pid)

    for packet in valid_incoming:
        pid = packet.id
        if pid in index:
            # Same packet seen from a parallel node.
            # Union ack_by so no acknowledgment from any parallel branch is lost.
            # This is the correct reconciliation, NOT a length comparison.
            merged_ack = index[pid].ack_by | packet.ack_by
            if merged_ack != index[pid].ack_by:
                index[pid] = packet.model_copy(update={"ack_by": merged_ack})
        else:
            # Truly new packet: append in insertion order.
            index[pid] = packet
            order.append(pid)

    return [index[pid] for pid in order]


def merge_task_threads(
    existing: dict[str, list[ChatMessage]] | None, new_item: dict[str, list[ChatMessage]] | Any
) -> dict[str, list[ChatMessage]]:
    """
    Merge strategy for task_threads channel.

    Structure: {thread_id: [ChatMessage, ...]}

    • Task-focused conversation management
    • Merges conversation lists by thread ID
    • Reuses append_chat_messages logic for smart duplicate detection per thread
    • Clean separation by task execution context
    """
    existing = existing or {}

    if not isinstance(new_item, dict):
        return existing

    # Deep copy existing to avoid mutation
    result = {}
    for thread_id, messages in existing.items():
        result[thread_id] = list(messages) if messages else []

    # Merge new task thread conversations using append_chat_messages logic
    for thread_id, new_messages in new_item.items():
        if not isinstance(new_messages, list):
            continue

        # Get existing messages for this thread (or empty list)
        existing_thread_messages = result.get(thread_id, [])

        # Use append_chat_messages to handle smart merging for this thread
        merged_messages = append_chat_messages(existing_thread_messages, new_messages)

        # Update result with merged messages
        result[thread_id] = merged_messages

    return result


def merge_threads(
    existing: dict[str, Any] | None, new_item: dict[str, Any] | Any
) -> dict[str, Any]:
    """
    Merge strategy for threads channel.

    Structure: {thread_id: Thread}

    • Thread metadata management
    • Overwrites existing threads with new data
    • Preserves existing threads not in new_item
    """
    existing = existing or {}

    if not isinstance(new_item, dict):
        return existing

    # Create result by copying existing
    result = existing.copy()

    # Overwrite with new thread data
    for thread_id, thread_data in new_item.items():
        result[thread_id] = thread_data

    return result


def merge_workspaces(
    existing: dict[str, Any] | None, new_item: dict[str, Any] | Any
) -> dict[str, Any]:
    """
    Merge strategy for workspaces channel.

    Structure: {thread_id: Workspace}

    • Workspace data management
    • Overwrites existing workspaces with new data
    • Preserves existing workspaces not in new_item
    """
    existing = existing or {}

    if not isinstance(new_item, dict):
        return existing

    # Create result by copying existing
    result = existing.copy()

    # Overwrite with new workspace data
    for thread_id, workspace_data in new_item.items():
        result[thread_id] = workspace_data

    return result
