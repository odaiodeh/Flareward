# Inter-element messaging contracts

This package defines graph-independent packet models and interfaces:

- `models.py`: addresses, packet kinds and error values.
- `packets.py`: task, system and debug packets with identities, TTLs and acknowledgments.
- `interfaces.py`: messenger and middleware contracts.
- `exceptions.py`: protocol failures.

`mas.graph.messaging.GraphInterMessenger` implements these contracts over declared
`GraphState` channels. `mas.graph.capabilities.messaging.GraphMessagingMixin`
binds that implementation to graph nodes. Sending validates the sender and adjacent
destination, copies packet data, and validates scope after middleware. The addressed
receiver owns acknowledgment; outgoing routing excludes acknowledged/expired packets.
Broadcast creates distinct packet identities. Node capabilities declare their channel
reads/writes and use the normal construction/invocation path.

These controls support cooperative graph nodes; they are not a security boundary
against arbitrary code sharing a Python process. Graph-local packets are distinct
from Program-level durable waits/messages, which use the application runtime port
and Run Engine coordination. Task threads are workload data, not child executions.

The old core messenger/factory/utilities and application graph-capability namespaces
are removed. Import the current owners directly. Focused graph-message contracts and
saved-agent session integration tests cover this path; remote recovery and scale
require their own acceptance evidence.
