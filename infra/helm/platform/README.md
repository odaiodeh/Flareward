# Native Program platform deployment

The API and durable worker use the same Python 3.14 platform image. Its entrypoint
is `lumora-platform`; the API chart supplies `serve --host 0.0.0.0 --port <service.port>`
and the worker chart supplies `worker`. No ROLE/Gunicorn/old Temporal CLI is used.
Build and verify the image using [the package guide](../../platform/README.md#native-service-image).

Configure existing shared services and private secrets before installation:

- Override `env.LUMORA_HOST` with the same Temporal endpoint, namespace and task
  queue on API and worker. The example defaults use `temporal:7233` and do not
  discover the actual service address.
- Set `LUMORA_MONGO_URI` and optional database explicitly. Native configuration
  does not use old MONGODB_IP/RABBITMQ_IP/BACKEND_ENV settings.
- Supply the API's `LUMORA_SECRET_KEY` and `LUMORA_IDENTITY_URL` through the configured
  shared Secret/ConfigMap. Use session authentication for the normal UI.
- Configure native Redis interactions, library/authoring, receiver credentials,
  encryption and managed workflow access as needed using the package development
  guide. Keep secrets out of Helm command arguments and committed values.
- Set the same installed application/element modules, applicable placement policies
  and credential-purpose settings on API and worker. Configure a suitable durable
  environment journal when retained remote environments are enabled.

The charts reference shared ConfigMaps/Secrets and existing storage; they do not
provision Mongo, Redis, Temporal or private credential delivery. Configure those
references, image repository/tag and service addresses in deployment values.

```sh
helm lint ./be
helm lint ./temporal-worker
helm template lumora-api ./be -f deployment-values.yaml
helm template lumora-worker ./temporal-worker -f deployment-values.yaml
```

After reviewing rendered output, deploy the charts using the normal environment's
release procedure. Use distinct release names and the same applicable runtime
configuration. The API probes `/api/health/health` on its configured service port.
The worker has no HTTP service or port. Its old `pgrep` probes were removed because
process-name matching does not establish task-queue readiness. Kubernetes still
restarts a terminated worker process; automated poller-based rollout readiness is
not implemented here and remains required deployment acceptance work.

Chart lint/render and an isolated Local image smoke test are separate from actual
cluster acceptance. Validate native poller readiness, API/worker recovery, durable
journals, replicas, private receiver delivery, isolation and cleanup before claiming
production Kubernetes/OpenShell readiness. The old service modules still awaiting
behavior migration/retirement are tracked in the active platform plan.
