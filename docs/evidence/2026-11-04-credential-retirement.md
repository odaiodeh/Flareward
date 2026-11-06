# Persisted workflow grant retirement (2026-11-04)

Closed-root authority was already denied at authentication, but the renewal-only
scan left fixed-expiry and not-yet-due grants persistently unrevoked. Changed the
owned repository ports and existing upkeep to visit bounded indexed pages of all
unrevoked grants. Known closed roots/current authorization withdrawal now persist
revocation before renewal becomes due. Missing pre-provisioned roots stay pending;
unknown native authority cannot extend or revoke an otherwise-valid grant.
Verification read/cancel-only scope retains its frozen-plan authority when creation
policy disappears, without acquiring create/run-check permission; it still retires
on expiry or root closure.

Expiry retirement needs no native lookup. It compares the observed expiry and
uses both application and Mongo clocks. A stale expired snapshot cannot revoke a
concurrently renewed lease; a fast application clock cannot retire a lease that
Mongo still considers live. Purpose services own authorization, while shared
`MongoCredentialLifecycle` owns bounded discovery and atomic expiry/renewal fences.
Removed the old renewal-only helper/import path rather than adding an alias.
Retired grants leave the scan and retain immutable issuance/scope/hash audit.
No additional scheduler or environment manager was introduced.

Evidence:

- **88 passed in 4.26 seconds**, `/tmp/unifai-credential-retirement-focused-20261104.xml`:
  application, real native liveness, HTTP lifespan and architecture guards. Includes
  fixed/not-yet-due grants, policy withdrawal, unknown authority, preserved pending
  roots, expiry without native access, capped renewal and bounded cursor behavior.
- **15 passed in 39.26 seconds**, `/tmp/unifai-credential-retirement-native-20261104.xml`:
  actual Mongo retirement/renewal CAS, database-clock fences, persisted fixed-grant
  retirement, a short renewing Human Review lease, and graph/backend composition
  across thread/process runners with approve/reject outcomes. Actual signed-cookie
  API/Mongo/Redis/native workflows assert persisted retirement after completion.
  The stale-snapshot test lets the old lease actually expire before attempting
  retirement, so it proves the expiry CAS independently of the clock fence.
- **1 production Human Review client journey passed in 3.28 seconds**, six unrelated
  cases deselected, `/tmp/unifai-credential-retirement-client-20261104.xml`. Actual
  TypeScript clients/TCP API/Mongo/Redis/native execution; no browser-gesture claim.
- **32 application lifecycle cases passed in 0.08 seconds**,
  `/tmp/unifai-credential-retirement-policy-final-20261104.xml`. This final small
  gate adds the fixed/renewable read-cancel policy distinction after the preceding
  gates. Production source is unchanged; no native/client gate was repeated for
  this test-only addition. The 32 cases overlap the 88-case gate.
- Strict mypy passes for six affected production modules; affected Ruff checks,
  both diagnostic skill validators and `git diff --check` pass.

Source manifest: `/tmp/unifai-credential-retirement-source-20261104.json`, 1,698
code/test/package files; aggregate SHA-256
`c78244c10ad4a1d825c12107940307fffcecdd7485b2aa23a3453aeb075a5343`.
Prepared/Program/state/element formats are unchanged. Run Engine remains unchanged
at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

Metadata retirement is eventual under bounded upkeep capacity/outages; root/expiry
authentication enforcement remains independent. This is not atomic external-effect
fencing, private-file collection or complete credential lifecycle. No paid provider,
image build, broad Temporal/replay or Kubernetes/OpenShell gate ran. Matched images,
process-restart/replay and remote cleanup acceptance remain at their milestones.
The overall goal was active when this checkpoint was recorded; this is historical evidence, not live goal status.

Extracted from the [frozen historical record](archive/execution-platform-migration-2026-11-04.md#persisted-workflow-grant-retirement-2026-11-04). Newer work is tracked in [current status](../status.md).
