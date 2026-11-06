---
name: refactor-agent-boundaries
description: Refactor UnifAI shared agent code and element plugins while preserving portable references, construction behavior, dependency direction and resource ownership.
---

# Refactor agent and plugin boundaries

Read [the current package status](../../../docs/program-platform-development.md#package-boundaries)
before moving modules. Shared values live in `mas.domain`; application behavior and
ports live in `mas.application`. Catalog/construction contracts and services live
in `mas.application.elements`; portable bundles are domain data. Discovery belongs
to an outbound adapter composed by `bootstrap.elements`, not the registry.
Concrete plugins currently retain their existing
`mas.elements` registrations. Classify responsibilities before moving a whole tree;
putting a mixed package under `adapters` does not fix its dependencies.

Program values/bindings live in `mas.domain.programs`; authoring, registry,
publication, ports and blueprint import live in `mas.application.programs`.
Placement values, step metadata and the shared frozen base have domain owners.
Import shared values from those owners rather than re-exporting them through
Program models. The old `mas.programs` namespace and core placement module are
retired. The domain cold-import check must not initialize application code;
retired paths must stay unimportable in the checkout and installed receiver images.
Update all actual import/portable-function consumers and packaging guidance.

Execution context, lifecycle records, request digests and safe placement values
live in `mas.domain.execution`. Submission requests, prepared adapter snapshots,
delivery claims, lifecycle services/ports and the mutable context holder live in
`mas.application.execution`. Domain context must not import its holder. The old
execution package/core context module are retired without aliases. Missing context
identity is invalid; do not restore the removed unknown-owner backfill or silently
ignore extra fields. Metadata tags are JSON-only. Preserve team-owner versus
acting-human credential semantics through receiver round trips.

Incomplete configuration needs schema-aware protection before persistence. Do not
use `model_construct` over raw nested dictionaries as a validation workaround:
those dictionaries remain untyped, so model-instance secret traversal loses their
declared private-field metadata. Keep draft completeness separate from strict
publication/construction validation. Exercise nested models, aliases, unions and
embedded registered bundles before claiming generic partial-configuration support.

The implemented `ConfigurationDraft` keeps incomplete fields with their installed
schema metadata; it is not a runtime Pydantic instance. `ConfigurationSecrets`
protects supplied values recursively, including registered resource configurations
inside bundles. Complete construction remains a publication/compilation invariant.
Validate authored snapshots as one traversal, rather than resolving every resource
as a separate root (which becomes quadratic for deep shared chains). Preserve
canonical field names through category factory revalidation (`by_name=True`).

Reusable `application.agents`, `application.workloads` and `application.capabilities`
packages cold-import without `mas.graph`. Workload services take `WorkloadStorage`;
they do not select graph/memory implementations or retain old convenience facades.
`mas.graph.workloads.GraphWorkloadStorage` binds the graph channels. Graph nodes use
`graph.capabilities.workloads.GraphWorkloadMixin` and
`graph.capabilities.messaging.GraphMessagingMixin`; generic agent/tool behavior
stays in the application. Shared delegation policy accepts candidate mappings;
only the orchestrator plugin interprets finalizer topology.

`core.iem` contains portable interfaces/packets. The graph-state transport is
`graph.messaging.GraphInterMessenger`; obsolete core factories/messenger/utilities
and old capability imports are removed without aliases. Preserve copied packet
ownership, sender/destination checks, destination acknowledgments and declared
channel writes. This is cooperative graph-local messaging, not a secure broker or
Run Engine's durable Program message/wait mechanism. Use `test_workloads.py`,
`test_graph_workloads.py`, `test_graph_messaging.py` and saved-agent session tests.

Generic specifications and construction must cold-import without graph state.
Graph node/condition declarations specialize `GraphElementSpec` and graph-specific
protocols in `mas.application.programs.graph_elements`; generic operations and
dependency resources do not inherit channel reads/writes. Keep abstract spec bases
out of discovery and registration, while concrete descendants validate normally.
Operations use their invocation key and typed context, never a fabricated
`StepContext` or automatic graph `set_context` injection. Test coincidentally named
methods: structural protocol matching alone does not authorize graph binding.
Current receiver/prepared formats are `unifai-elements-v3` and `runengine/request-v10`;
old prototype payloads have no compatibility promise. Rebuild matched images at
the next relevant milestone after these installed-source changes.

Backend Program invocation/model enforcement belongs to application `ApplicationInvoker`.
Adapter `ApplicationCall` only captures/resolves installed references and translates
boundary errors; it must not become another validation service or implementation
registry. Program entrypoint contract is `unifai-program-v5`. Keep validators/defaults/
serializers deterministic and runtime effects behind application ports. Registration
already serves the installed specification role; introduce implementation classes or
factories for real cohesive behavior/construction needs, not structural symmetry.

Declared backend child contracts use application `ChildContracts` / `ChildContract`
and the same `ProgramContracts` validator as graph calls. Keep configured mappings,
scope schemas and consumed result contracts separate from child execution handles.
Map/Repeat runtime scope construction uses the same named models as admission.
Unknown structure requires runtime checks; do not assert arbitrary Python analysis
or build another registry/scheduler to validate these declarations.

Whole-value `Projection` is portable domain data. Typed operation/Program inputs
may be any JSON shape; graph input and output channel writes remain named mappings.
Application `ProgramState` owns read-only `input`, indexed `results`, writable channel
schemas and safe update validation. The thin engine adapter binds native reducer
behavior (`unifai-graph-state-v3`). `StateContracts` admits declared channel access
and graph-wide ordered/reduce writer policies; receiving adapters check actual
returned changes against declared writes. Reduce uses existing reducers, including
overwrite; it is not a general concurrency guarantee. Installed operations still receive
only selected JSON and operation context. Do not push graph state into generic specs,
factories, construction or invocation ports. Result indexing is current graph data,
not authoritative occurrence history or artifact storage.

Schema documents and conservative navigation belong to application
`programs.interfaces`; scoped graph input/result references belong to `graph_data`.
`ProgramContracts` composes those with catalog/call validation. Keep schemas in their
original reference context instead of flattening foreign `$defs`. Graph join policy
is a domain enum lowered only by the engine adapter. Do not import SDK enums into
application models or implement another scheduler to analyze read dependencies.

`GraphFlow` owns bounded static activation/reachability, separate from schema
navigation and native scheduling. Canonical sources choose ordinary edges or
conditional branches; mixed modes are draft-only. Blueprint import normalizes
redundant branch `after` metadata and rejects unmapped conditional dependencies.
Do not silently discard authored edges to satisfy native routing precedence. Label
normalization has no magic `END` exception. Keep unknown cyclic/complex activation
guarantees subject to runtime contracts rather than claiming they were proven.

The target is a fresh platform. Move useful behavior into its proper layer and
update current callers/tests. Remove superseded execution modules, aliases, old
formats and dependencies; no old-worker or stored-history preservation is required.
Batch related module moves into a coherent milestone before rebuilding current
receiver images and verifying installed references. Use focused boundary/contract
checks between milestones. Keep active cancellation and resource cleanup safe.

Cycles exposed by extraction often identify mixed responsibilities:

- Tool request/response values should not construct retry policies and validators.
  Runtime construction presets belong in the executor configuration module.
- Parser error types must be importable without initializing parser registration
  and defaults. Keep them in the separate agent error module.
- Work-item retry invariants belong to the work item, not a service it imports.
- Tool JSON Schema validation must not import `global_utils.utils.util`, which
  initializes shared infrastructure configuration. Use the declared schema directly.
- Graph adjacency/card values belong to domain data. Importing their old aggregate
  card package can pull plugin namespaces into otherwise clean agent imports.
- Native async preparation belongs inside the already owned construction scope,
  before building dependents. Register ownership before awaiting acquisition so
  preparation failures and cancellation cannot strand returned instances.

Do not deep-copy collaborator ports when converting runtime configuration to
constructor arguments: it can clone resource-owning clients. Snapshot collection
containers while borrowing their members. Check nested mutable defaults/schema
data separately; frozen model fields do not imply deeply immutable values.

Use the static and cold-import guards in `tests/architecture/test_boundaries.py`.
They cover the extracted layers, module-level imports and hidden initializer
dependencies. Verify domain/workspace round trips and shared-agent contracts first,
then run saved-resource/blueprint/session E2E and native replay through
[the platform test workflow](../run-platform-tests/SKILL.md). Keep application test
harnesses composed from production capabilities and narrow port doubles; registered
node behavior belongs in integration scenarios using the existing builders.

At the installed-module milestone, rebuild and verify both receiver images, load
the Kubernetes image into the dedicated test cluster and run the selected remote
matrix once against the frozen source. Do not repeat this heavy sequence after
each individual move or import cleanup. Record exact results and remaining
unverified scope. A passing import test
does not establish the correctness of every plugin or completion of the migration.

Image verification checks current-file hashes, canonical Program imports and
absence of retired paths. Use the same frozen source across build, verification
and deployment tests. Preserve active owned resources and inspect their identities
before cleanup; an old-looking sandbox name alone does not establish ownership.
