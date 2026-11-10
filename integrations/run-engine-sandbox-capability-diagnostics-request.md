# Request: distinguish unsupported sandbox capabilities from transient relay failure

Status: diagnostic capability request, not a request to weaken isolation or a
confirmed scheduling bug. Inspected Run Engine baseline:
`60393440efd3876cd6c81e0b013e8bf6d9167659`; no companion changes were made.

Lumora's current OpenShell candidate profile requires Landlock. On this Docker
Desktop kernel, the supervisor exits with:

```text
Landlock unavailable in hard_requirement mode:
not implemented (kernel lacks CONFIG_SECURITY_LANDLOCK)
```

Refusal is correct. A capable Linux host is required for this profile; changing
Lumora or retrying cannot add a missing kernel capability. The diagnostic issue is
that readiness can be observed briefly before supervisor exit. Invocation then
reports `UNAVAILABLE`, `exec relay closed before the command reported an exit status`,
or a disconnected supervisor/SSH channel. Lumora receives a retryable infrastructure
failure with no stable capability code. Repeated retries obscure a permanent
deployment prerequisite. See [scoped evidence](../docs/evidence/2026-11-05-candidate-profile.md).

Please identify an existing public capability/status contract if it already covers
this. Otherwise consider surfacing a stable unsupported-isolation/capability result
when the backend can establish it authoritatively. This may require an upstream
OpenShell status signal; generic transport errors alone cannot prove permanence.

- Preserve hard requirements and fail closed before candidate execution.
- Keep capability diagnosis and physical lifecycle in the engine/backend adapter;
  Lumora should not parse supervisor text or inspect Docker from application code.
- Distinguish unsupported capability from transient relay disconnection, worker
  loss and unknown status. Do not classify every relay error as permanent.
- Return safe capability/profile context without invocation data or credential
  material. Avoid exposing private SDK fields as the application contract.
- Preserve owned cleanup across startup failure, invocation-owned/retained scopes,
  cancellation and unavailable observations.

Acceptance should include unsupported versus supported capability, the brief-ready
race, genuine relay outage and cleanup. A supported Linux host should still execute
the real positive/restricted/offline policy cases. This request does not establish
that those cases pass or replace Lumora's remaining strict-profile acceptance.
