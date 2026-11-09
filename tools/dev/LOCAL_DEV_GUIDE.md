# Local development

Python 3.14, Node 22+, npm/pnpm, tmux and Docker/Podman are required for the full
stack. Install `tools/dev` to use the optional `flareward-dev` service manager:

```sh
.venv/bin/python -m pip install -e tools/dev
flareward-dev init
flareward-dev start
flareward-dev start platform --fg
flareward-dev logs platform -f
```

The registry in `services.yaml` defines Platform, Identity, UI and an optional
Temporal worker. `init` generates local environment files; supply your authorized
Identity configuration. All services using signed sessions must share the generated
secret and Redis. See [authentication](AUTH_AND_SESSIONS.md).

Use [the platform guide](../../platform/README.md) for explicit package and
API/worker commands and its named Run Engine dependency. A Local host needs no
Temporal worker; a Temporal host needs a separately started matching worker.
Use [the UI guide](../../ui/README.md) for standalone UI development. Vite proxies
`/api` to Platform and `/identity/api` to Identity using `PLATFORM_HOST` and
`IDENTITY_HOST`.

Dedicated regression services and remote test images belong to
`platform/tests/infra`. They deliberately use different ports from ordinary dev
services. Do not stop unrelated containers or bind the same ports to another stack.
