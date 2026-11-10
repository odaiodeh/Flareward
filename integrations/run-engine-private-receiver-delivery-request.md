# Request: private material delivery to isolated invocation receivers

Status: capability request, not a confirmed Run Engine bug. Inspected baseline:
`60393440efd3876cd6c81e0b013e8bf6d9167659`. Lumora has not changed the companion
checkout. Please identify an existing public capability if it already covers this.

Lumora provisions bounded workflow credentials for an approved owner/root. Its
trusted Local receivers resolve them from a private filesystem. Kubernetes and
OpenShell receivers need only the credential for their admitted root and purpose;
they must not receive the vault key or the directory containing all roots. Raw
credential bytes cannot enter portable runner configuration, invocation arguments,
results, logs or durable coordination history.

The public `InvocationExecutorBuilder.register` supports custom factories, and
`EnvironmentDriver` supports retained environment creation/invocation. Those
ports alone do not expose a verified native invocation origin and an out-of-band
setup hook for the actual invocation-owned Kubernetes pod or managed OpenShell
sandbox. Their built-in executors create the physical receiver internally. Static
Kubernetes Secret mounts and pre-existing OpenShell sandboxes can be configured by
operators, but do not establish automatic per-root delivery for all lifetimes.
Portable `InvocationRequest` arguments and metadata are application data and must
not independently establish authority. See `runengine/invocation/ports.py`,
`runengine/invocation/ownership.py`, the Kubernetes/OpenShell executor and driver
implementations, and `runengine/bootstrap/registry.py` at the baseline above.

Please consider a public extension point that lets a trusted application-owned
provider, configured on the dispatcher rather than in portable requests:

- Receive an engine-established invocation/run generation and verified environment
  use, sufficient to correlate the invocation with the admitted root. Lumora owns
  the mapping to its owner, purpose and grant; untrusted context fields are hints,
  never proof. Wrong roots, stale generations and revoked uses fail closed.
- Deliver narrowly scoped private material to the actual receiver through an
  out-of-band channel before its invocation starts, with no material in replayable
  data or backend configuration. Support invocation-owned and retained environments,
  including explicitly borrowed uses; do not transfer ownership to the borrower.
- Define cleanup, cancellation, timeout, concurrent use, uncertain acknowledgments,
  worker loss and retry semantics. Successful work must not be repeated solely
  because credential cleanup failed. A delayed setup must not resurrect a retired
  binding or overwrite a later generation.
- Keep the engine responsible for physical resource identity, environment grants
  and lifetime. Keep application approval, grant issuance, scope, audit, rotation
  and material retirement in Lumora. Avoid a second sandbox manager or reliance
  on private SDK fields/journals.

Workflow capabilities delivered into a workload are accessible to code with the
same OS identity; their scope must therefore authorize only that root's allowed
operations. Human reviewer authority and provider/infrastructure credentials must
not be delivered as workflow credentials. The separate [environment file-I/O
proposal](run-engine-environment-file-io-request.md) addresses trusted transfers
whose credential must remain outside untrusted workloads entirely.

Acceptance should cover Kubernetes and OpenShell, invocation-owned and retained
environments, parent/child borrowing, concurrent roots, explicit cancellation,
worker restart, replay, late writes, deletion and cleanup failures. Verify that a
receiver cannot resolve another root's material and that neither private material
nor controller credentials appear in histories, payloads, logs or results. No such
remote proof is claimed here.
