"""
IEM Packet Models

Base packet for transport layer and specific packet implementations.
Clean separation between transport concerns and payload.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, Field

from lumora.elements.messaging.protocol.models import ElementAddress, PacketType
from lumora.elements.workloads.domain import Task


class BaseIEMPacket(BaseModel):
    """
    Base packet for all IEM communications.

    Handles transport layer concerns: routing, acknowledgment, lifecycle.
    Domain-agnostic - doesn't know about specific payload content.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    protocol: str = "iem/2.0"
    type: str
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ttl: timedelta | None = None
    src: ElementAddress
    dst: ElementAddress

    ack_by: set[str] = Field(default_factory=set)

    @property
    def is_expired(self) -> bool:
        """Check if packet has expired based on TTL."""
        return self.ttl is not None and (datetime.now(UTC) - self.ts) > self.ttl

    def acknowledge(self, uid: str) -> None:
        """Mark packet as acknowledged by given uid."""
        self.ack_by.add(uid)

    def is_acknowledged_by(self, uid: str) -> bool:
        """Check if packet is acknowledged by given uid."""
        return uid in self.ack_by

    def is_acknowledged(self):
        return bool(self.ack_by)


class TaskPacket(BaseIEMPacket):
    """
    Task packet that carries task payload.

    Transport layer handles routing, acknowledgment, lifecycle.
    Task payload handles agentic business logic and coordination.
    """

    type: Literal[PacketType.TASK] = PacketType.TASK
    payload: dict[str, Any]

    @classmethod
    def create(cls, src: ElementAddress, dst: ElementAddress, task: Task, **kwargs) -> TaskPacket:
        return cls(src=src, dst=dst, payload=task.model_dump(), **kwargs)

    def extract_task(self) -> Task:
        return Task.model_validate(self.payload)


class SystemPacket(BaseIEMPacket):
    """System packet for system-level communication."""

    type: Literal[PacketType.SYSTEM] = PacketType.SYSTEM
    system_event: str
    data: dict[str, Any] = Field(default_factory=dict)


class DebugPacket(BaseIEMPacket):
    """Debug packet for development and debugging."""

    type: Literal[PacketType.DEBUG] = PacketType.DEBUG
    debug_info: dict[str, Any] = Field(default_factory=dict)


IEMPacket = Annotated[
    TaskPacket | SystemPacket | DebugPacket,
    Discriminator("type"),
]
