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

Check consumers, package initializers, factory/spec discovery and persisted engine
references. Element bundles freeze specification references; native entrypoints and
graph state references are separate contracts. Preserve actual persisted contracts
or document a migration/drain boundary. Internal Python import compatibility alone
does not justify a forwarding package. Keep old workers on their compatible release
while their executions drain.

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

After installed-module moves, rebuild and verify both receiver images, load the
Kubernetes image into the dedicated test cluster and run the selected remote
matrix. Record exact results and remaining unverified scope. A passing import test
does not establish the correctness of every plugin or completion of the migration.
