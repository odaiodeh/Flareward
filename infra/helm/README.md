# Lumora deployment charts

Run Helmfile from this directory. The retained release groups are:

- `shared-resources.yaml.gotmpl`: Mongo, Redis, Temporal and optional inspection/logging.
- `identity.yaml.gotmpl`: authentication and directory service.
- `platform.yaml.gotmpl`: canonical FastAPI service and Temporal worker.
- `ui.yaml.gotmpl`: UI and same-origin API proxy.

Supply operator-managed values/secrets and a tested image tag before deployment.
API and worker must share the same host/namespace/task queue and compatible source.
Build with the named Run Engine source context documented in `platform/README.md`.
UI proxy configuration uses `PLATFORM_IP`/`PLATFORM_PORT` and Identity service values.
RAG ingestion and the old admin backend are retired. Their releases and hooks are
removed; this change does not uninstall existing releases in external clusters.

Use `platform/tests/infra` for owned local tests. Production chart deployment is
separate from test acceptance and requires the target environment's authorization.
