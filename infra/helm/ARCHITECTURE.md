# Deployment ownership

`platform` owns the HTTP and worker releases. Both install `flareward-platform` and
use its `serve` / `worker` commands. `identity` authenticates humans; `ui` proxies
`/api` to platform and `/identity/api` to Identity. Shared Mongo/Redis/Temporal are
external infrastructure, not imported application components.

Charts and release groups are described in [the deployment guide](README.md).
See [the platform architecture](../../docs/architecture/README.md) for contracts,
plugin installation and feature ownership. No RAG/admin application is deployed.
