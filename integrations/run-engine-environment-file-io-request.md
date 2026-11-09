# Investigate scoped out-of-band environment file I/O

Status: capability proposal for strict workload isolation, not a confirmed engine
bug or a prerequisite for the current trusted-workload transfer path. No companion
source change has been made. Checked SDK baseline: `60393440efd3876cd6c81e0b013e8bf6d9167659`.

## Current evidence

Flareward can publish and materialize managed blobs through registered operations.
Application services enforce artifact ownership, capabilities, integrity and byte
limits. Credentials use protected configuration or a receiver-private file; only
portable blob references appear in program results. Local thread/process handoff
after workspace deletion and API restart is verified.

This credential handling does not isolate a private file from arbitrary hostile
code running as its owning OS user. A strict deployment should allow a trusted
transfer component to move permitted workspace bytes without putting its artifact
credential into the coding/test environment. That also keeps infrastructure
credentials outside arbitrary repository code.

The checked public `EnvironmentBindingOperations` exposes declaration, borrowing,
resolution and grant release; `BoundInvocationDispatcher` exposes bound invocation.
`ResolvedEnvironment` retains a logical use and immutable target specification.
The checked public environment ports do not expose a portable streaming file I/O
contract. Kubernetes/OpenShell drivers own their physical identities internally.
We must not bypass those owners by reading private journals or inventing another
environment manager in Flareward.

Sources: `runengine/invocation/environments.py`,
`runengine/coordination/environments.py`, and each backend's
`adapters/invocation/{kubernetes,openshell}/environment.py` in the baseline above.

## Proposed contract to discuss with the engine owner

Prefer an existing public capability if one already satisfies these requirements.
Otherwise consider a narrow environment file-I/O port usable by trusted invocation
effects outside the untrusted workload:

- Address an existing owner generation / validated borrowed use. Do not accept
  arbitrary backend resource IDs as authority.
- Read or write an admitted relative workspace file through a bounded async stream.
  Keep bytes and private application credentials outside coordination histories;
  the Flareward effect returns a small application reference/receipt.
- Verify the physical resource identity and grant before access. Preserve the
  borrower's lack of deletion authority.
- Constrain roots, symlinks, special files, byte counts and write replacement.
  Define atomic completion, cancellation, timeout, uncertain acknowledgement and
  active-transfer behavior during owner cleanup.
- Make the capability available through the public host/runtime composition. Avoid
  asking Flareward to instantiate private drivers or reconstruct environment records.

Flareward still owns artifact ACLs, storage, content identity, repository/candidate
semantics, evidence and acceptance. The engine owns environment identity, grants,
transport and lifetime. No ADLC classes or artifact-store service belong in the SDK.

## Acceptance scenario

1. A run owns a Kubernetes/OpenShell environment; a child borrows it explicitly.
2. Untrusted code produces a file while the transfer credential stays outside that
   environment. A trusted effect exports only the admitted file and publishes it.
3. A different run materializes the verified bytes after the first environment is
   destroyed. Only small receipts/references appear in native history.
4. Wrong-owner, stale-generation, revoked-grant, symlink-escape and oversized
   requests fail without file or credential disclosure.
5. Exercise cancellation, lost acknowledgement, worker restart and native replay;
   cleanup drains or fences active transfers and never deletes another owner.
6. A malicious repository process cannot read the transfer credential through files,
   environment variables or command arguments in its workload environment.

This proposal does not claim those security/failure scenarios currently pass.
Continue unrelated platform work while this contract is investigated.
