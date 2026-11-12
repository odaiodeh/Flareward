# Configured interfaces and published dependency expectations

Scope: Step A of the [coordinator milestone](../architecture/coordinator-programs/README.md).
This advances C2/C4. It does not complete dependency discovery/authoring, the milestone,
or the larger platform goal.

## Implemented contracts

Typed configuration may implement `ConfiguredInterface.program_interface()` and
return `ProgramSchemas`. These optional raw-input and serialized-output constraints
freeze alongside authored and installed-model schemas in the published interface.
Each document retains its own reference scope. Publication rejects provable
contradictions; composition checks literals and known paths against refinements.
Unknown dynamic facts retain runtime checks. This is not unchecked schema merging
or a claim to statically understand arbitrary Pydantic coercion/validators.

Map's configured `max_items` and Repeat's `max_iterations` now constrain their
published input/result contracts. Root admission rejects invalid raw input before
creating an execution. Native workers enforce configured output constraints after
model normalization. Re-resolved configured contracts must match the publication
before custom coordinator effects.

Custom coordinator `ChildContracts` declarations now freeze as typed portable
`DependencyInterface` values: named request projections, scope schemas, consumed
result projections, result-model validation schemas and explicit result schemas.
No live Python models enter this contract. Target revisions, owned bodies and
explicit environment imports remain in the immutable definition. Restored declared
names must have bound targets. Missing/malformed declarations reject safely.
Admission and worker invocation detect changed expectations before effects.

The existing pure `programs/domain/bindings.py` module now owns binding values as
well as projection evaluation, avoiding a definitions/interfaces import cycle.
All current Python callers use that owner; no model-module compatibility aliases
remain. Evaluation behavior is preserved. Graph bindings remain frozen in typed
graph definitions, rather than acquiring another editable declaration copy.

The production invocation form chooses the published configured input schema when
present. Additional authored refinements remain server-enforced; a complete
multi-schema authoring/form renderer and normalized-input observation remain open.

Current native Program contract is `lumora-program-v9`. Recreate old publications
and prepared payloads; rebuild matched workers for the remote gate. A same-schema
Python behavior change still requires implementation versioning.

## Tested source

Lumora HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`, plus uncommitted work.
Source/test delta SHA-256: `66ceacc3cbaf081c3b79a85916bb8c8b6157becf1ca3603a3cec1002eb7df90d`.
Digest uses `git diff --binary -- platform/src platform/tests ui/client ui/tests`,
then sorted untracked paths, NUL and file bytes in those directories.
Run Engine remains at `60393440efd3876cd6c81e0b013e8bf6d9167659`; no upstream edits.

## Verification

From the repository root:

```sh
.venv/bin/python -m pytest platform/tests/domain platform/tests/application platform/tests/adapters/run_engine platform/tests/adapters/test_program_repository.py platform/tests/architecture platform/tests/integration/run_engine/test_programs.py platform/tests/integration/run_engine/test_composition.py platform/tests/integration/run_engine/test_program_models.py -q --tb=short --maxfail=3
```

**1,008 passed.** Includes configured snapshot immutability, invalid declaration
returns/schemas, disjoint contracts, pinned/owned caller refusal, input admission
before records, output rejection, dependency expectation drift and native worker
refusal before runtime calls. Existing local composition and architecture tests
remain green. Earlier 998/64/43-test checkpoints overlap this gate.

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/mongo/test_program_repository.py 'platform/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[programs]' --ui-clients -q --tb=short --maxfail=2
```

**9 passed.** Actual Mongo publication contracts and the production TypeScript
client journey against TCP FastAPI with the existing signed-session harness.
The client publishes Map with a two-item maximum, observes its frozen schema,
receives HTTP 422 for three items, and completes the valid two-item composition.

From `ui`, both pass:

```sh
pnpm --config.verify-deps-before-run=false run typecheck
pnpm --config.verify-deps-before-run=false run test:contracts
```

Changed Python files pass Ruff `I,F821,F822,F823,E9`. All inspected Python callers
use the current binding owner; `git diff --check` passes. Intermediate failures
were a missing TypeScript error-guard import and a binding-module extraction that
omitted the existing evaluator. Both were corrected before the gates above.

No current-source browser, Temporal recovery, Kubernetes, OpenShell, paid-provider,
image or scalability gate was run here. Those remain scheduled at the coherent
milestone boundary; historical images cannot certify v9. Declaration discovery and
editing, remaining C1-C4 audit, review composition/routing, observation and the
full workspace remain subsequent work.
