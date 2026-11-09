# Flareward naming and namespace cutover

Flareward is the platform's public name. Use `Flareward` in product text,
`flareward` in Python and machine-readable identifiers, and `FLAREWARD_` for
platform environment variables. The repository folder can have any local name. This checkout is now at
`/Users/odaiodeh/IdeaProjects/Flareward`, with `origin` set to
`git@github.com:odaiodeh/Flareward.git`; `main` tracks `origin/main`.

## Canonical names

| Surface | Name |
| --- | --- |
| Product, UI, API description | Flareward |
| Core source and imports | `platform/src/flareward/`, `flareward.*` |
| Capability implementation source and imports | `platform/src/plugins/`, `plugins.*` |
| Python distribution and API/worker command | `flareward-platform` |
| Developer distribution, command and fallback script | `flareward-dev`, `tools/dev/flareward-dev` |
| UI package | `flareward-ui` |
| Application configuration | `FLAREWARD_*` |
| Dedicated test configuration | `FLAREWARD_TEST_*`, `FLAREWARD_E2E_*` |
| Images | `flareward-platform`, `flareward-receiver`, `flareward-sandbox`, `flareward-codex` |
| Independent test stack and kind cluster | `flareward-e2e` |

Installed capability plugins use the top-level `plugins` package. The core's
`flareward.plugins` module owns the pure manifest contract; it does not contain
concrete capability implementations. Composition roots select installed plugins.
The generic `global_utils` shared infrastructure package and the external
`runengine` package keep their own names.

## Installing and configuring

This is a namespace and runtime-contract cutover, without old-name aliases.
For an existing development environment, uninstall the old distribution before
installing the renamed packages:

```sh
.venv/bin/python -m pip uninstall unifai-platform unifai-dev
.venv/bin/python -m pip install -e ./packages/service-support -e './platform[dev]' -e ./tools/dev
```

Rename `UNIFAI_*` settings to `FLAREWARD_*` in private environment files, deployment
secrets and process configuration. Change installed module references from
`unifai.*` to `flareward.*`, and plugin references to `plugins.*`. API, worker and
receivers must use the same installed modules, configuration and rebuilt images.
See [platform startup](../platform/README.md) and
[the dedicated infrastructure guide](../platform/tests/infra/README.md).

New defaults use the Flareward database, queue, storage/log paths, capability
identifiers, markers and test resource names. Existing databases, volumes, queues,
credentials, signed grants and published revisions are not renamed or deleted by
this source change. Recreate publications and grants for this fresh platform;
do not resume old histories using renamed workers. If retaining a deployment's
existing data location, configure its database/storage/queue explicitly and plan
a separate data conversion rather than substituting strings in stored records.
Do not run old and renamed workers against the same active task queue.

## External identities and historical records

A source rename does not rename external repositories, GitHub secrets, registry
namespaces, domains, Slack channels or existing Docker/Kubernetes resources.
The active repository is now `odaiodeh/Flareward`; GitHub redirects its prior
`odaiodeh/UnifAI-ADLC` address. The original community repository and private
certificate repository retain their actual `UnifAI` addresses, as does the
`UNIFAI_SECRETS_TOKEN` GitHub secret.
Jenkins credential IDs (`github-unifai-token`, `images.paas.registry-unifai`),
the existing Vault path and downstream Jenkins job also retain their actual
external identities. The certificate checkout directory is `ui/Flareward-secrets`; original certificate
filenames are copied to generic `server.pem` / `server.key` paths in the image.
Existing external deployment/support links remain their actual addresses until
operators migrate those services. Renamed deployment manifests target Flareward
release/image/storage names and require provisioning those resources before use.
The checkout move preserves uncommitted work and repairs local Python/Node
environment paths and the owned idle test gateway mount. Reopen the new folder
in Codex and the IDE. No commit, push, deployment, credential rotation or data
deletion is performed by this cutover.

Files in `docs/evidence/` describe their original tested snapshots. Preserve old
names, image digests, source manifests and captured media in historical evidence.
A later rename does not change what an earlier test executed. New evidence uses
the current names. Historical references are not compatibility entry points.
