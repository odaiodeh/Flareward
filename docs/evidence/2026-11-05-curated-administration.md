# Native curated-resource administration checkpoint

Curated resource CRUD, dependency publication, protected editing and cooperative
leases now use native application ports and HTTP routes. The existing Repository
Management screen and production resource clients use these contracts, including
the exact loaded version for edit, visibility and delete. They no longer treat an
unavailable edit lease as a successful acquisition. This is an administration
capability checkpoint within unfinished native runtime convergence.

## Ownership and invariants

`BuiltinAdministration` owns acting-human authorization through the generic
`AdministratorAccess` port, the complete dependency closure, intended visibility,
loaded-version conflicts and cooperative editor checks. Resource configuration
preparation is shared with ordinary authoring through `ResourceConfiguration` and
the existing schemas/secret protection; factories and element registration remain.
The Mongo directory has its own adapter, separate from reporting. Selected team
ownership never supplies administrator authority, and human routes reject bearers.

Publications reject missing, cyclic, unsupported or inconsistent construction
references before mutation. Dependency closures are bounded. Resource/descriptor
changes commit together through snapshot transactions; a real index failure rolls
back every earlier write. Every observed dependency, even an already-public one,
is checked and fenced. An inward-only `storage_revision` captures Mongo's internal
fence: without that check, a transaction can still commit a stale decision prepared
before a competing publication committed. The public resource version remains the
editor's distinct optimistic concurrency contract. Public dependents block demotion.

Redis leases remain cooperative coordination, not an atomic Redis/Mongo lock.
Protected admin configuration remains encrypted, public views remove reusable
ciphertext, and caller-editable credentials keep identity-specific overlays. Delete
removes the selected resource, descriptor and its overlays together after usage
checks. Native errors are safe, with no partial-write fallback on standalone Mongo.
Incoming-reference checks do not prove catalog-wide concurrent authoring integrity.

The old 771-line built-in service, 440-line Flask endpoint module and unused update
DTO are removed. The field-alias secret regression uses native overlay ports.
The retained sharing cloner takes its narrow descriptor reader directly rather
than depending on administration. Static/cold-import checks reject the removed
service and show the new application module imports no graph/plugin/SDK packages.

## Verified results

From the repository root:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain multi-agent/tests/architecture -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_MONGO_TRANSACTION_URI='mongodb://127.0.0.1:27019/?directConnection=true' UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_builtin_administration.py multi-agent/tests/integration/mongo/test_builtin_standalone.py multi-agent/tests/integration/http/test_builtin_administration.py multi-agent/tests/integration/mongo/test_builtin_configuration.py multi-agent/tests/integration/mongo/test_resource_authoring.py multi-agent/tests/integration/mongo/test_reporting.py multi-agent/tests/integration/http/test_reporting.py multi-agent/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services --ui-clients -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

- **666 shared-layer tests passed**, 6.68s. Includes dependency/visibility policy,
  human-versus-team authority, private configuration and stale version/foreign lease
  refusal, plus existing application/domain/architecture coverage.
- **25 native cases passed**, 44.33s, no skips. Actual transaction rollback,
  competing publication/demotion, atomic overlay cleanup, standalone refusal,
  signed-session HTTP/Redis authorization/leases/revocation and production TS clients.
  Existing resource/overlay/reporting and editor-client regressions are included.
- Strict mypy passed for **13 production modules**: the new application, shared
  access/reporting/editing contracts, directory/admin/resource Mongo adapters,
  configuration/authoring, native admin/resource routers and library/platform roots.
  Use `MYPYPATH=lib:adapters:plugins:. ../.venv/bin/mypy --strict --follow-imports=silent`
  from `multi-agent` with those explicit module paths.
- Ruff lint/format passed on **31 files**, enumerated in the source manifest.
  UI `npm run typecheck`, direct cold import, skill frontmatter validation and
  `git diff --check` passed. Browser rendering was not exercised.

Initial development checks found a team test parametrizing the newly forbidden
admin kind and missing precise annotations. Design review also identified the
transaction-fence race above. Explicit team refusal replaces the invalid parametrization.
An initial Compose inspection lacked the required state-directory variable and
made no infrastructure change; the command with the existing owned state path
then created only the new Mongo transaction service. All final gates passed.

The exercised Python/client source was frozen during gates. Subsequent cleanup
changed whitespace and the response factory's return annotation to `Self`; strict
typing and the native HTTP/client journey were checked again. Client review then
found the shared form dropped curated operation placement preferences. Create/edit/
detail state now carries them; a final native production-client journey passed in
3.19s, including stored process-to-thread preference changes and cleanup. UI typing
was rerun. This verifies configured defaults, not physical placement. Detailed source
identity is in the [46-file manifest](2026-11-05-curated-administration-source.json),
with two removed paths. Its path/hash-map aggregate SHA-256 is
`82a3e44bd02620ff454e9406bfc39863ebaef3980a8487a90290cbbd91575c6e`.
This is a focused source identity, not a full-source/image or load acceptance claim.

## Infrastructure and remaining acceptance

The optional UnifAI `transactions` Compose profile owns `mongo-transactions` on
loopback port 27019; ordinary Mongo/Redis/Temporal were not restarted. Its image is
`sha256:e0ce8c35124d4a9f9785532d1f268f39e9728ffa1cb38f46fa482436424c4bd3`.
The single-node replica is healthy and intentionally retained for reuse. Per-test
databases, API processes, signed sessions and owned leases are cleaned by fixtures.
The shared Mongo fixture now always closes its client even if database cleanup
fails. The image identity does not establish failover or transaction-load capacity.

Registered test elements and HTTP peers are deterministic; no paid model was called.
No service/receiver image rebuild, Temporal/Kubernetes/OpenShell or actual-browser
matrix ran. The image verifier now rejects the retired service; actual installed
absence needs the queued coherent runtime-retirement build. Admin draft-provider
probes, remaining credential administration, sharing/template migration, full old
runtime removal, catalog-wide races, transaction failover/capacity and all broader
platform acceptance remain open. Run Engine was not changed.
