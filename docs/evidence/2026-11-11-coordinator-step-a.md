# Coordinator Step A: contracts, dependency discovery and local acceptance

Step A of the [coordinator milestone](../architecture/coordinator-programs/README.md)
is accepted at its domain/application/adapter/HTTP/client verification boundary.
Step B is active. C1-C4 do not certify C5-C10, the full browser workspace, matched
remote workers, recovery matrices, scalability, or the larger platform target.

## Working authoring behavior

The existing Program editor now discovers required dependency names from unsaved
coordinator configuration. `POST /api/catalog/programs/interface` returns a typed
`ProgramInterfacePreview`, including configured schemas and declared dependency
expectations. Typed configuration parsing no longer requires bindings to exist.
Publication separately rejects missing targets as `INVALID_BINDING` at the exact
`implementation / children / name` source. Compatibility and authorization still
run through existing publication/admission services.

`ProgramService.preview_interface` resolves only the selected coordinator. It does
not fetch target revisions, read Resource sources, construct capabilities, save a
draft, grant authority or allocate compute. Native graph preview can describe an
unfinished graph without treating it as executable. Invalid/incomplete configuration
returns safe issues without echoing private values or inventing dependency names.
The HTTP endpoint requires authentication and returns private/no-store metadata.

The UI debounces requests, cancels obsolete work and gates displayed results by
request/owner identity. Configuration stays out of shared query caches. The existing
picker binds declared names to pinned revisions; expected contracts are available
through progressive disclosure. Bound inline bodies remain visible, and adding
other explicit bindings remains available. Full inline/nested authoring is Step C.
Removing a binding removes its existing imports; replacing its target preserves
imports for validation. The target inspector now reads its frozen interface.

## Acceptance map

| Criterion | Current code and evidence |
| --- | --- |
| C1: shared specification/catalog/lifecycle | `programs/registry.py`, `bootstrap/plugins.py`, `bootstrap/programs.py`: native `graph@1` plus explicit installed plugin manifests. Catalog tests exercise a plugin contributing both Elements and Programs; typed/custom fixtures register and execute without core-service special cases. |
| C2: resolved frozen interfaces | `programs/signatures.py`, `domain/interfaces.py`, `contracts.py`, `invocation.py`: authored, configured, validation and canonical documents retain separate scopes. Published-interface/configured-interface/model/binding tests cover aliases, nested references, RootModel arrays, invalid outputs, pinned/owned contracts and declaration drift. Production client verifies frozen limits and invocation. |
| C3: Resource capture parity | `elements/construction/configuration_resources.py`, `snapshots.py`, `ProgramService`: graph scopes and typed nested configuration destinations, including owned bodies. Application and real Mongo/native thread/process tests verify source adoption, ownership, protected credentials, frozen revisions and unchanged reruns. Existing picker/production client supplies selection commands. |
| C4: consistent dependencies | `ProgramBody.dependencies`, configured `ChildContracts`, frozen `DependencyInterface`, shared compiler preparation: pinned/owned targets, source paths and explicit imports. Native tests exercise graph→graph, graph→custom, custom→graph and custom→custom calls; owned/pinned tests verify independent/unchanged reuse. Adapter tests prove no implicit environment grant and preserve imports/placement ownership. Actual remote lifecycle proof remains C9. |

This builds on [published interfaces](2026-11-11-published-interfaces.md),
[Resource capture](2026-11-11-configuration-resources.md) and
[configured contracts](2026-11-11-configured-contracts.md). Their earlier image and
runtime scopes remain historical; the current gate below is the Step A scope.

## Tested source

Lumora HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`, plus uncommitted work.
Source/test delta SHA-256: `12e0653b8cad5caebdb2a98de14b4da3129914d8dd9114bf74b5d31b4552dc94`.
Digest uses `git diff --binary -- platform/src platform/tests ui/client ui/tests`,
then sorted untracked paths, NUL and file bytes. The sole change after the broad
run was the corrected test assertion described below; production source stayed fixed.
Run Engine remains `60393440efd3876cd6c81e0b013e8bf6d9167659`; no upstream edits.
Program payload remains v9; current matched remote images are still required at D.

## Verification

```sh
.venv/bin/python -m pytest platform/tests/domain platform/tests/application platform/tests/adapters/run_engine platform/tests/adapters/test_program_repository.py platform/tests/architecture platform/tests/integration/catalog platform/tests/integration/http/test_programs.py platform/tests/integration/run_engine/test_programs.py platform/tests/integration/run_engine/test_composition.py platform/tests/integration/run_engine/test_program_models.py -q --tb=short --maxfail=3
```

**1,077 passed; one obsolete assertion failed.** The implementation correctly
rejected a missing dependency with its new binding diagnostic. The old test expected
“Invalid configuration”. It now asserts `ProgramContractError`, `INVALID_BINDING`
and the exact dependency path; its focused rerun below **passed**. No production
code changed to accommodate the test, and no scoped test remains failing.

```sh
.venv/bin/python -m pytest platform/tests/application/test_composition.py::test_missing_composition_children_fail_before_publication -q --tb=short
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/mongo/test_program_repository.py platform/tests/integration/mongo/test_resource_snapshots.py -q --tb=short --maxfail=2
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest 'platform/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[programs]' --ui-clients -q --tb=short --maxfail=1
```

Respectively **1**, **16**, and **1** passed. Persistence scenarios use dedicated
Mongo; Resource stories execute on real Local thread/process runners. The production
TypeScript client uses TCP FastAPI and the signed-session harness. It previews an
unbound Map without creating a Program, saves the unfinished draft, observes the
missing binding path, binds/publishes, compares preview and frozen dependency
contracts, and executes the composition. Other existing client journeys remain green.

From `ui`, typecheck, contract tests and production build pass. Render contracts
verify required unbound selectors, including a dependency named `constructor` that
must not resolve to an inherited JavaScript property. The build retains the existing
warning about chunks above 500 kB. Changed Python passes Ruff `I,F821,F822,F823,E9`;
`git diff --check` and the diagnostics skill validator pass.

No actual-browser, Temporal recovery, Kubernetes/OpenShell, paid-provider or load
suite ran here. UI cancellation/stale-response behavior is implemented but its
interactive browser acceptance belongs to C/D. Configuration preview intentionally
does not certify topology, target authority, compatibility or placement. Arbitrary
Python semantics remain versioned implementation behavior, not schema proof.

## Next work

Step B replaces ADLC Design/Engineering's direct `human_review(...)` and embedded
`HumanReviewConfig` coupling with configured reviewer Program dependencies, while
preserving exact candidate/evidence checks, durable decisions and recovery. Generic
result routing and the mixed graph/Repeat/attempt journey follow in the same step.
