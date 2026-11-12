# Explicit coordinator strategies — 2026-11-12

Scope: the requested registration/terminology refinement, on the preserved
uncommitted coordinator milestone worktree. This does not complete steps B-D.

## Implementation

- `CoordinatorRegistration.strategy` is required and typed as
  `NativeGraphStrategy | CustomCoordinatorStrategy`. Only the custom strategy has
  an entrypoint; it validates async behavior. Catalog kind derives from strategy.
- Native graph identity/configuration cannot be registered as a custom strategy,
  and native registrations cannot enter custom preparation or invocation.
- Canonical names are `CustomCoordinatorDefinition`, `CoordinatorEntrypoint`,
  `CoordinatorCall`, and the plugin export `COORDINATORS`. Source, fixtures, UI
  types, active docs and relevant guidance were updated without aliases.
- Publication, prepared execution and graph/custom composition retain their
  shared contracts. Serialized `kind: application` remains the custom-definition
  discriminator; it is not a separate public lifecycle. Request/Program formats
  remain v10; there is no new wire field or execution mechanism.
- New regression cases cover invalid strategy/spec combinations, native/custom
  boundary refusal, and portable custom strategy/model resolution. Existing
  async-entrypoint and native composition cases exercise the updated convention.

## Verification

- Focused catalog/invocation/interface/native composition/architecture: 107 passed
  in 7.14s. Includes all four graph/custom combinations on the Local host and
  thread/process receivers where parameterized; application cases use ports.
- Wider domain/application/adapter run: 1,060 passed before three localhost
  telemetry-server binds were denied by the filesystem/network sandbox. All
  domain/application cases completed. The adapter suite was then rerun with
  localhost permission: all 212 passed in 4.83s. Together these runs cover all
  1,137 selected cases; counts overlap the focused run and must not be added.
- Plugin-manifest discovery: 1 passed; native graph, core controls and the Human
  Review plugin use the same catalog with explicit strategies.
- Full platform collection: 1,972 tests collected without import errors.
- TypeScript passed with `tsc --noEmit --incremental false`. The ordinary command
  initially failed only because its incremental cache write was sandbox-denied.
- Changed Python imports/undefined-name/syntax lint passed; diff whitespace passed.

No paid calls, remote images, Temporal recovery or browser acceptance were run.
Deploy API, workers and receivers with matched installed coordinator modules;
older plugin exports are intentionally not retained as compatibility aliases.
