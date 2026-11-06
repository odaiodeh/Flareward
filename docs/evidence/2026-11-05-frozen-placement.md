# Frozen event source placement

Compilation now records a safe placement tree alongside the private engine request.
It includes Program revision/body identity, defaults, owned environment profiles,
declared child imports, and static graph node/operation/condition selections. A
borrowed environment's profile is left unresolved in its child; backend Programs
are marked dynamic because their invocation choices cannot generally be inferred
statically. This is admitted intent, not observation of actual invocations.

The owner-scoped event source settings API returns the frozen tree. It excludes
backend configuration, resource payloads and credentials. Preparation identity
covers the summary, and the gateway refuses a summary that differs from the
compiled request. Binding a later event retains the originally approved tree.
The prepared Run Engine format is now `runengine/request-v10`; old prototype
snapshots are not migrated and worker images must be rebuilt before remote proof.

Verification: 74 focused application, adapter, Local composition and architecture
cases passed; 7 scheduled admission/application cases passed; the real TypeScript
client -> FastAPI -> dedicated MongoDB/Redis -> Local execution journey passed.
UI TypeScript typecheck, Ruff and strict mypy on six production Python modules
passed. Tests cover nested imported environments, pinned-template revision changes,
and summary tampering. No browser journey or Temporal/Kubernetes/OpenShell run was
performed. Arbitrary runtime choices and actual execution placements still require
the authoritative observation milestone.

The 11 changed source/client/test files have aggregate SHA-256
`c3cfbda83daac1d444c98d3bd87206d942a93c20c6fa24cc530dc33a4f77bbc0`,
over a sorted compact JSON path-to-file-hash map.
