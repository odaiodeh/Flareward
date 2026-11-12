# Published Program interfaces — 2026-11-11

Step A progress in the [coordinator milestone](../architecture/coordinator-programs/README.md).
This is not completion of C1–C10 or the overall platform goal.

## Implemented boundary

- `ProgramRevision.interface` persists coordinator identity/version, public raw
  input/output constraints, installed model validation schemas, canonical serialized
  schemas and owned-body interfaces. Each schema retains its bundled reference scope.
- `ProgramInterfaces` captures detached snapshots. Publication integrity and both
  repositories' source-idempotency checks include the resolved interface. Conflicting
  interfaces cannot be published as the same draft version. Reads remain detached.
- Application composition checks consume pinned dependency interfaces; owned targets
  use interfaces resolved from their enclosing definition. Admission compares the
  installed declarations with the frozen revision before execution preparation.
- Program v8 payloads carry the selected body's interface without its descendant
  snapshots. The application invoker rejects changed identities/model schemas before
  custom coordinator effects and validates normalized values against frozen schemas.
  Native graph payloads reject incompatible coordinator/normalizer metadata.
- UI invocation reads the selected revision's input contract. The production client
  journey verifies immutable contracts after later draft edits and actual invocation.
- Aliases/defaults, custom validation, canonical/computed fields, array values and
  schema-local references remain separate from raw-input JSON Schema enforcement.

The domain stores portable values; resolution/normalization stay in application
services. SDK function references and native graph delegation remain in the Run
Engine adapter. No companion-project source was changed.

## Tested source

Lumora HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`, with uncommitted changes.
Source/test delta SHA-256: `958ef6861d2a97d1383debd700ab760a2d8f3f73d9a450ba5f571125147931ba`.
The digest covers `git diff --binary -- platform/src platform/tests ui/client ui/tests`
followed by each sorted untracked file's path, NUL and bytes within those directories.
Run Engine: `60393440efd3876cd6c81e0b013e8bf6d9167659`.

## Verification

Commands run from the Lumora checkout with its existing Python 3.14 venv:

```sh
.venv/bin/python -m pytest platform/tests/domain platform/tests/application platform/tests/adapters/run_engine platform/tests/adapters/test_program_repository.py platform/tests/architecture platform/tests/integration/run_engine/test_programs.py platform/tests/integration/run_engine/test_composition.py platform/tests/integration/run_engine/test_program_models.py -q --tb=short --maxfail=4
```

**965 passed.** Includes native Local Program/composition/model behavior and
architecture boundaries. After safe invalid-schema handling and three additional
reference/alias/schema regressions, the affected tests were rerun:

```sh
.venv/bin/python -m pytest platform/tests/application/test_published_interfaces.py platform/tests/application/test_program_invocation.py platform/tests/integration/run_engine/test_program_models.py -q --tb=short --maxfail=2
```

**43 passed.** These overlap the broad gate and are not an additive test count.
The worker-drift case prepares a real request, changes the model resolved by the
worker, invokes the native entrypoint, and checks refusal before runtime calls.

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/mongo/test_program_repository.py 'platform/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[programs]' --ui-clients -q --tb=short --maxfail=2
```

**9 passed.** Dedicated existing services, real Mongo persistence and TCP FastAPI,
thread/process authoring executions, and production TypeScript Program clients.
The interface conflict/detachment scenario is shared by memory and Mongo adapters.

From `ui`:

```sh
pnpm --config.verify-deps-before-run=false run typecheck
pnpm --config.verify-deps-before-run=false run test:contracts
```

Both passed. Changed Python files pass Ruff `I,F821,F822,F823,E9`; `git diff --check`
passes. Intermediate test failures during implementation were corrected; the results
above are the subsequent passing checks. No unresolved failure in this scoped gate.

## Limits and next work

Generated schemas cannot fingerprint arbitrary Python validators/serializers;
semantic changes require an implementation version change even with identical schemas.
Configuration-derived interface refinements and separately observed normalized inputs
remain unfinished. Old revisions lack the required snapshot and must be republished;
old prepared payloads must be regenerated. No compatibility fallback was added.

Next in Step A: resource save/adoption parity for nested coordinator configurations
and remaining declared dependency/interface refinements. Review-as-child adoption,
generic routing, occurrence correlation and nested UI follow the agreed order.

No Temporal replay/restart rerun, browser journey, image rebuild, Kubernetes/OpenShell
acceptance or paid provider call ran in this gate. Earlier receiver images do not
certify Program v8; rebuild and verify them at Step D. No commit or push was performed.
