---
description: SOLID, hexagonal boundaries, minimal class-oriented Python, validated contracts, native async lifetimes, and safe error handling.
globs:
  - "**/*.py"
---

# Engineering standards

Follow the user's task and the applicable architecture. For the platform
platform, start/resume with `docs/status.md` and `docs/plan.md`. Search and read
relevant sections of `docs/architecture/README.md` and the development guide;
retrieve specific proof through `docs/evidence/README.md`. Do not load full guides
or historical archives by default. Rewrite compact status/plan facts and keep
detailed milestone results in evidence records. The full goal/target still define
completion. Historical implementation patterns do not override the target.
The fresh platform platform has no requirement to retain superseded APIs,
formats, workers, aliases, or compatibility facades. Other services consuming
shared libraries retain their own contracts unless their migration is authorized.

## Cohesive, minimal design

- Give each class a cohesive responsibility and explicit dependencies. Prefer
  composition and narrow interfaces; keep subclasses substitutable.
- Use classes for related behavior, policies, services, and owned lifecycles.
  Small stateless helpers can remain functions in their owning module. Do not
  introduce a class, base class, facade, or interface solely for ceremony.
- Extend registered capabilities through specifications, factories, and plugins.
  Do not add integration-specific compiler branches or competing registries.
- Split services along independent responsibilities, not an arbitrary method
  count. Avoid global discovery state, singleton lookup, service locators, hidden
  dependencies, circular imports, and duplicate implementations.

## Hexagonal ownership

| Layer | Owns | Depends on |
| --- | --- | --- |
| Domain | Values, invariants, outcomes and business rules | Domain values and minimal validation types |
| Application | Use cases, policy, operation contracts and ports | Domain and application-owned interfaces |
| Adapters/plugins | HTTP/SDK/database/filesystem/process integration | The inward contracts they implement or call |
| Composition root | Registration, configuration and concrete wiring | Application, adapters and plugins |

`platform/src/lumora` is organized by feature; each feature owns its values,
ports, services and adapters locally. `platform/src/plugins` contains
feature-owned integrations and reusable Programs. Assess
ownership by responsibility and imports, not just the top-level directory.
Domain/application contracts must not import concrete plugins, transport layers,
provider SDKs, database drivers, or execution SDK types. Concrete integrations
import inward. Inbound adapters call application services; outbound adapters
implement application-owned ports. Keep infrastructure adapters cooperating through
explicit contracts and owned composition, without moving business policy outward.

Use ABCs or Protocols when they express a real substitutable boundary. There is
no rule requiring exactly one ABC per adapter class. Pure payload mappers, wire
models and composition helpers need no artificial application port. Vendor-neutral
behavior belongs inward; vendor integration belongs in the plugin/adapter ring.
Run Engine owns scheduling, durable coordination and physical environment
lifetimes. Lumora owns application policies and translates through its ports.

## Models, types and enums

- Use Pydantic for validated configuration, API, invocation and portable-data
  boundaries. Use ordinary classes or dataclasses internally where additional
  runtime validation serves no purpose. Use safe mutable defaults and appropriate
  constraints. Freeze values that should be immutable.
- Use enums for closed statuses and policies. Extensible plugin/program/type
  identities remain strings with explicit versions where required; adding a
  plugin must not require editing a central enum.
- Annotate production interfaces, signatures and return values precisely. Avoid
  unstructured dictionaries for known contracts and `Any` where a useful type is
  available. JSON Schema and extensible JSON payloads need appropriately typed
  mappings, not a separate model for every possible user-defined field.
- Do not duplicate validation/models across layers without a distinct contract.
  Keep raw SDK settings and private credentials outside public application/UI data.

## Async execution and ownership

- Use native async I/O and explicit async resource lifetimes. Pure computation,
  constructors and ordinary factories may remain synchronous.
- Avoid nested event loops, async bridges and blocking I/O on the event loop.
  If a required dependency is synchronous, isolate the blocking adapter operation
  and retain ownership until it has stopped before releasing its resources.
- Own acquisitions, tasks, clients and subprocesses explicitly. Drain or cancel
  owned work and close partially constructed resources on success and failure.
  Cancellation must propagate after cleanup; never report it as successful work.
- Keep shared compute, mutable workspace files, conversation state and durable
  artifacts distinct. A borrowed environment does not transfer deletion rights.

## Imports and error semantics

- Put imports at the top of files: standard library, dependencies, local modules.
  Use type-only imports when appropriate, avoid wildcard imports and repair cycles.
  Optional plugin selection belongs in explicit composition, not hidden imports
  inside business functions.
- Use meaningful application exceptions. Translate technical failures at adapter
  boundaries without leaking SDK classes, credentials, input values or raw private
  diagnostics. Do not hide failures with empty success results or silent fallback.
- Broad exception handling belongs at deliberate translation/cleanup boundaries;
  preserve cancellation and failure classification. Include only safe context.
- Keep names precise, public interfaces small and comments focused on non-obvious
  ownership/invariants. Remove dead code and replaced guidance with the old path.

## Process, file and test discipline

- Use argument lists for subprocess execution. Avoid shell interpretation of
  user-derived values. Shell quoting is necessary only when intentionally building
  shell text; do not quote arguments passed directly to an executable.
- Create secret files privately from the start. Scope filesystem access, validate
  containment where required, bound resource use and clean only owned resources.
- Tests follow the same boundaries as production code. Use owned-port doubles for
  application policy and actual adapters for integration evidence. Reuse cohesive
  scenario fixtures, not test inheritance hierarchies or another scheduler.
- Verify actual behavior and failure ownership. Keep paid-provider cases opt-in.
  Record exact gate results and limitations; passing tests do not prove perfection,
  architectural completion, or production scalability.
