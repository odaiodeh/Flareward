# Reusable workloads and explicit graph integration

Reusable agent policy, workload services and shared capability packages now
cold-import without graph state. `WorkloadStorage` is the application-owned
synchronous state port; `UnifiedWorkloadService`, `ThreadService` and
`WorkspaceService` receive it rather than constructing storage. Message-context
synchronization accepts messages and is named `sync_messages` rather than referring
to graph state. The one remaining caller of the old workload convenience facade
now uses the actual thread service. Unused concrete-memory construction and facade
methods were removed, not retained as compatibility aliases.

Graph binding lives in `mas.graph.workloads.GraphWorkloadStorage` and
`mas.graph.capabilities.workloads.GraphWorkloadMixin`. Messaging binding lives in
`mas.graph.capabilities.messaging.GraphMessagingMixin` and
`mas.graph.messaging.GraphInterMessenger`. Installed nodes/conditions import these
explicit graph components. Portable IEM packet/interface modules import no graph.
The old application mixin namespaces and core graph messenger/factory/utilities
were removed, including unused request-routing placeholders and testing factories.
No new operation/program lifecycle, scheduler or broker was introduced.

Generic delegation policy snapshots candidate identities and filters plain mappings;
the orchestrator plugin alone interprets finalizer topology. Its redundant filter
override and unused diagnostic helpers were removed. Typed base `Channel` now
explicitly enumerates the base schema rather than constructing an untyped dynamic
enum. A schema-coverage invariant prevents missing base names; custom Program
channels remain validated string names. Schema metadata introspection handles
mapping versus callback metadata without assuming every value has `.get`.

## Behavioral checks

Graph transport copies packets before storage and detaches inbox reads. Sender and
adjacent destination are validated after middleware; only the destination can
acknowledge a packet. Routing checks acknowledgment by that destination rather than
any arbitrary actor. Purging is local to the recipient. Broadcast creates distinct
packet IDs; read-only views cannot publish. These are cooperative in-process
contracts, not a security boundary against hostile Python sharing the state object.

The shared workload scenario exercises the same application services with a narrow
memory port double and the real graph storage implementation: hierarchy, workspace
content, service rebinding and child deletion. Graph data is serialized/restored
and decoded to domain values. Independent tests cover injected work-plan streaming
hooks, generic candidate filtering and the actual orchestrator's finalizer exclusions.

## Verification

From the repository root, final-source checks:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain multi-agent/tests/architecture -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_agent_sessions.py multi-agent/tests/integration/catalog/test_discovery.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
.venv/bin/python -m pytest multi-agent/tests/integration/catalog/test_delegation_policy.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

Results: 638 domain/application/architecture tests passed in 5.31s; 15 native/catalog
tests passed in 7.88s; two orchestrator-policy tests passed in 0.01s. No skips were
reported. Saved sessions exercise actual Mongo, the HTTP adapter via ASGI, Local
thread/process receivers, transitive saved resources, two agent turns, evidence
tools, context continuity and packet acknowledgments. These are not TCP-separated
API/worker, Temporal, Redis-delivery or browser E2E claims.

The initial graph round-trip assertion compared untyped Python datetime dictionaries
to JSON dictionaries. It was corrected to compare decoded domain values. Typing
first exposed the dynamic enum and metadata callback assumptions; both were fixed
before the final gates. A preceding 637-test pass predates the typed-channel change
and does not replace the final-source 638-test gate.

From `multi-agent`, strict typing passed on seven production modules:

```sh
MYPYPATH=lib:adapters:plugins:. ../.venv/bin/mypy --strict --follow-imports=silent lib/mas/application/workloads/storage.py lib/mas/application/workloads/unified_service.py lib/mas/application/agents/delegation_policy.py lib/mas/graph/workloads.py lib/mas/graph/messaging.py lib/mas/elements/nodes/orchestrator/delegation_policy.py lib/mas/graph/state/graph_state.py
```

Ruff lint/format checks passed on 31 source/test files. Their hashes and five
explicitly absent modules are in the [source manifest](2026-11-05-graph-boundaries-source.json).
Aggregate SHA-256 over its sorted compact JSON map:
`736479a4e3d5b289e21deea7ba2788acc484a7d907a361610cd1c0a62672492f`.
This is a focused source checkpoint, not a full deployment/image manifest.
Exercised source was frozen during the final gates.

In `ui`, `node tests/run-api-contracts.mjs contracts` passed the production graph
and session-output contracts with existing dependencies. `pnpm run test:contracts`
first attempted an automatic package-manager/install check and failed on restricted
registry access/noninteractive module-purge confirmation. The direct script then
passed without installing or changing dependencies. No browser journey is claimed.

The existing refactoring skill was updated and passed `quick_validate.py`; messaging
and development documentation now identify actual owners and removed paths.

## Remaining acceptance

This closes the identified reusable workload/graph coupling checkpoint, not the
whole package/dead-code audit. Graph nodes and conditions intentionally retain graph
contracts. Large existing node implementations and moved dynamic mixins are not
covered by the seven-module strict-typing claim. The old Flask bootstrap, CLI,
Temporal runner and deployment entrypoint still need migration/retirement; the
container entrypoint currently launches the old command and its base Dockerfile
targets Python 3.12 despite the package's Python 3.14 requirement.

Current-image Temporal/Kubernetes/OpenShell, replay/restart, remote ownership and
cleanup acceptance remain pending the planned milestone. No Docker build, paid
provider or remote gate ran, and no Run Engine source changed. Shared workload
services do not claim a distributed transaction or cross-invocation locking.
