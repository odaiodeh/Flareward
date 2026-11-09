---
name: debug-builtin-administration
description: Diagnose or extend Flareward curated resource publication, administration, dependency visibility, private configuration, version conflicts and editor leases.
---

# Diagnose curated resource administration

Trace the Repository Management screen through `api/resources.ts`, native
`flareward.api.builtin_administration`, application `BuiltinAdministration`
and `flareward.resources.adapters.mongo.builtin_administration`. Canonical administration routes are
`/api/administration/resources`; the old built-in Flask routes/service are removed.
Ordinary resource reads and caller overlays still use the native resource service.

Human authority is distinct from selected workspace ownership. Application
`AdministratorAccess` decides authority through the persisted directory and explicit
flareward.bootstrap policy. An empty persisted list denies everyone; directory failure cannot
restore flareward.bootstrap access. Never derive human authority from `userId`, team selection
or workflow bearers. The inbound human principal rejects bearer-plus-cookie requests.

Custom and curated saves share `ResourceConfiguration` and installed schemas,
factories and secret metadata. Admin edit responses carry protected ciphertext,
never plaintext; public resource projections also remove reusable ciphertext.
Caller-configurable private fields come from the selected identity's own overlay.
Keep schema aliases, transitive construction references and frozen source identity.

Publication validates a bounded, acyclic dependency closure before writing. Missing,
unsupported or inconsistent references fail before publication. Root updates pin the
loaded resource version. Cooperative Redis leases coordinate administrators; they
are not a cross-store transactional lock. Do not turn unavailable leases into a
successful acquisition. Lease release remains bound to the actual human.
The shared form also supplies `execution`; preserve it in curated create/edit/detail
state rather than dropping placement preferences while mapping configuration fields.

Mongo commits resource/descriptor changes atomically using snapshot transactions.
Standalone Mongo must refuse mutations without partial-write fallback. The observed
set includes every dependency, including already-public dependencies. `_admin_fence`
is exposed only inward as `ResourceRecord.storage_revision`; it must be captured on
reads, checked and monotonically advanced on commit. Transaction conflicts alone
do not reject a stale dependency check prepared before a competing commit. Preserve
both the stored revision check and transactional writes when changing this adapter.

The dedicated infrastructure has an optional `transactions` Compose profile on
localhost 27019. Inspect its ownership before starting it; do not restart ordinary
Mongo/Redis/Temporal or unrelated containers. See
[the infrastructure guide](../../../platform/tests/infra/README.md).

Focused policy tests are `application/test_builtin_administration.py`, resource
configuration/encryption tests and architecture guards. Native acceptance uses:

```sh
FLAREWARD_TEST_MONGO_URI=mongodb://127.0.0.1:27018 FLAREWARD_TEST_MONGO_TRANSACTION_URI='mongodb://127.0.0.1:27019/?directConnection=true' FLAREWARD_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/mongo/test_builtin_administration.py platform/tests/integration/mongo/test_builtin_standalone.py platform/tests/integration/http/test_builtin_administration.py --ui-clients -q
```

The actual-store cases cover rollback on an index failure and competing publication/
demotion from stale observations. The signed-cookie HTTP case runs production TS
clients and deterministic registered capabilities. These do not establish browser
rendering, admin draft-provider probes, transaction failover, remote execution or
capacity. Keep those acceptance requirements explicit. Rebuild installed images at
the coherent runtime-retirement milestone through the platform test workflow.
