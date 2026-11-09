"""
HITL adapter implementations.

ChannelApprovalGate:              ApprovalGate backed by InputCapableChannel.
AutoResolvingApprovalGate:        Decorator that auto-resolves via shared OverridesStore.
ChannelApprovalGateFactory:       ApprovalGateFactory that assembles the full gate stack.
RedisOverridesStore:              OverridesStore backed by Redis for cross-process sync.
"""

from flareward.services.interactions.adapters.auto_resolving_gate import AutoResolvingApprovalGate
from flareward.services.interactions.adapters.channel_gate import ChannelApprovalGate
from flareward.services.interactions.adapters.gate_factory import ChannelApprovalGateFactory
from flareward.services.interactions.adapters.redis_overrides_store import RedisOverridesStore

__all__ = [
    "ChannelApprovalGate",
    "AutoResolvingApprovalGate",
    "ChannelApprovalGateFactory",
    "RedisOverridesStore",
]
