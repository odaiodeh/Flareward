# Lumora naming and namespace cutover

Lumora is the platform's public name. The name combines **lumen** (light) and
**aurora** (dawn), representing intelligence bringing ideas into reality.
Its tagline is **From intent to reality.**

Use `Lumora` in product text, `lumora` in Python and machine-readable identifiers,
and `LUMORA_` for platform environment variables. Capability implementations
continue to use the top-level `plugins` package. Directory names use lowercase
`lumora`, including certificate checkout directories such as `lumora-secrets`.

## Canonical names

| Surface | Name |
| --- | --- |
| Product, UI, API description | Lumora |
| Core source and imports | `platform/src/lumora/`, `lumora.*` |
| Capability implementation source and imports | `platform/src/plugins/`, `plugins.*` |
| Python distribution and API/worker command | `lumora-platform` |
| Developer distribution, command and fallback script | `lumora-dev`, `tools/dev/lumora-dev` |
| UI package | `lumora-ui` |
| Application configuration | `LUMORA_*` |
| Dedicated test configuration | `LUMORA_TEST_*`, `LUMORA_E2E_*` |
| Images | `lumora-platform`, `lumora-receiver`, `lumora-sandbox`, `lumora-codex` |
| New dedicated test stack and kind cluster | `lumora-e2e` |

The core's `lumora.plugins` module owns the pure manifest contract. Only bootstrap
selects concrete capability implementations. The generic `global_utils` shared
infrastructure package and the external `runengine` package keep their own names.

## Installing and configuring

This replaces the previous Flareward namespace without compatibility aliases.
Update an existing development environment before running the renamed entry points:

```sh
.venv/bin/python -m pip uninstall flareward-platform flareward-dev
.venv/bin/python -m pip install -e ./packages/service-support -e './platform[dev]' -e ./tools/dev
```

Rename `FLAREWARD_*` settings to `LUMORA_*` in private environment files, deployment
secrets and process configuration. Replace `flareward.*` module references with
`lumora.*`; `plugins.*` stays unchanged. Environments still using the earlier
UnifAI names need the equivalent `UNIFAI_*` and `unifai.*` cutover too.
API, workers and receivers must use matched installed modules and rebuilt images.
See [platform startup](../platform/README.md) and
[the dedicated infrastructure guide](../platform/tests/infra/README.md).

New defaults use Lumora database, queue, storage/log paths, capability identifiers,
markers and test resource names. Existing databases, volumes, queues, credentials,
signed grants, histories and published revisions are not renamed or deleted.
Recreate publications and grants for this fresh platform; do not resume old
histories using renamed workers. To retain an existing data location, configure
its database/storage/queue explicitly and plan a separate data conversion.
Do not run old and renamed workers against the same active task queue.

## External identities and historical records

The local checkout is `/Users/odaiodeh/IdeaProjects/lumora`, and `origin` uses
`git@github.com:odaiodeh/Lumora.git` for fetch and push. GitHub serves
`odaiodeh/Lumora` and redirects the old Flareward URL to the same repository.
`main` continues to track `origin/main`. The checkout move preserves the complete
uncommitted worktree and existing Git history, without an old-folder alias.
Generated Python/Node paths were repaired and editable packages reinstalled.
Reopen the `lumora` folder in Codex and the IDE so saved workspace selections follow
this move. No commit or push was performed. See the
[checkout verification](evidence/2026-11-10-lumora-checkout.md).

Existing external domains, GitHub secrets, registry credentials, Vault paths and
Jenkins jobs retain their actual identities. The original community repository
and private certificate repository retain their `UnifAI` addresses, as does the
`UNIFAI_SECRETS_TOKEN` secret. The certificate checkout directory is now
`ui/lumora-secrets`; original certificate filenames are copied to generic
`server.pem` / `server.key` image paths. Renamed deployment manifests require
provisioning the corresponding release/image/storage resources before use.

Existing Docker stacks and Kubernetes clusters retain their resource names.
The owned idle OpenShell gateway was recreated with its new absolute state mounts,
existing database and mTLS identities; other services were not stopped or changed. New defaults use `lumora-e2e`; do not start another stack on occupied
ports. Explicitly select existing owned services when reusing them for checks.
Fresh remote runs require rebuilt Lumora receivers, matched gateway configuration
and explicit image selection. Old images do not verify the renamed source.

Files in `docs/evidence/` describe their original tested snapshots. Preserve old
names, image digests, source manifests and captured media in historical evidence.
New evidence uses current names. Historical records are not compatibility paths.
