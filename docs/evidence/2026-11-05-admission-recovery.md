# Multi-purpose root admission recovery (2026-11-05)

This scoped backend slice extends [managed credential admission](2026-11-05-managed-credentials.md).
The full goal remains active. Event ingress, credential rotation, isolated remote
delivery, remaining recovery combinations and later platform milestones are open.

## Behavior and ownership

One existing submission claim owns provisioning for all requested purposes. A
partial grant commit or lost acknowledgment must not dispatch native work early.
Reconstructed application services reuse frozen human approval, prepared settings,
native identity and keyed reservations. Every purpose rechecks current policy.
Cancelled/refused roots retire their partial material through existing upkeep.
No scheduler, environment manager, second invocation path or SDK change was added.

The new Mongo cases exposed cancellation during recovery being classified as a
failure: the old path attempted issuance against its already-cancelled root.
Submission now checks cancellation before provisioning and again before dispatch.
An access refusal caused by concurrent cancellation also retains cancelled
semantics. Unrelated policy refusal remains failed. This is not stale-attempt
fencing for an external effect already in flight.

Root idempotency previously used Python equality for input data, equating booleans,
integers and floats. Canonical JSON comparison now distinguishes those values,
including nested data and racing first submissions, while accepting reordered
object keys. Native collision ownership is unchanged.

## Evidence

| Gate | Result | Report |
| --- | --- | --- |
| Initial application gate | 11 failed, 12 passed; missing new `json` import | `/tmp/unifai-multipurpose-unit-20261105.xml` |
| Corrected application gate | 23 passed, 0.16s | `/tmp/unifai-multipurpose-unit-corrected-20261105.xml` |
| Sandbox Mongo attempt | 1 setup error, 10.28s; loopback access denied | `/tmp/unifai-multipurpose-mongo-initial-20261105.xml` |
| Actual Mongo initial | 2 passed, 1 failed, 0.41s; stopped at cancellation regression | `/tmp/unifai-multipurpose-mongo-20261105.xml` |
| Corrected application/boundary | 37 passed, 3.08s | `/tmp/unifai-multipurpose-unit-boundaries-20261105.xml` |
| Corrected Mongo | 6 passed, 0.62s | `/tmp/unifai-multipurpose-mongo-corrected-20261105.xml` |
| Focused thread/process Temporal | 2 passed, 16.68s | `/tmp/unifai-multipurpose-native-20261105.xml` |
| Final cancellation-in-flight Mongo | 8 passed, 0.81s | `/tmp/unifai-multipurpose-mongo-final-20261105.xml` |
| Final application/boundary/Local recovery | 48 passed, 3.56s | `/tmp/unifai-multipurpose-final-contracts-20261105.xml` |
| Final production manual/Session clients | 2 passed, 8 deselected, 6.43s | `/tmp/unifai-multipurpose-client-final-20261105.xml` |

Mongo tests use production composition, encrypted reservations, purpose grant
repositories, private delivery and execution records. A narrow issuer-port wrapper
injects failure before the second purpose or after its committed result. The
execution gateway is a port double; these cases establish durable admission and
no early dispatch, not native execution. Eight competing requests observe the live
claim; twelve later retries share original authority after service reconstruction.
Retry, cancellation before/during issuance and policy withdrawal are checked.

The two native tests use actual signed-cookie HTTP, dedicated Mongo/Redis/Temporal,
and a separate live worker. Each profile runs two roots with four duplicate starts
per root. A graph requests verification, then invokes its pinned Human Review
Program; both use automatically provisioned purpose credentials. The API shuts
down and restarts at the same borrowed listening socket while the worker stays
live. Retrying preserves original approval/native identity. Cancelling one root
retires only its material; the other is still reviewed and completes successfully.
Both root/child histories replay; retired audit survives without ciphertext or
managed files. Portable responses and process logs contain no credential prefixes.
This is API-only restart during active automatic-access work, not an API-and-worker
restart or remote sandbox proof. Pending verification plans do not represent
trusted check acceptance; this scenario does not claim complete Engineering/ADLC.

## Reproduction and source boundaries

Use `.venv` and the dedicated service variables:
`UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018`,
`UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15`,
`UNIFAI_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7234`.

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_workflow_admission.py -q --tb=short --maxfail=1 --junitxml=/tmp/unifai-multipurpose-mongo-final-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_managed_workflow_recovery.py -q --tb=short --maxfail=1 --junitxml=/tmp/unifai-multipurpose-native-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/application/test_execution.py multi-agent/tests/architecture multi-agent/tests/integration/run_engine/test_recovery.py -q --tb=short --maxfail=1 --junitxml=/tmp/unifai-multipurpose-final-contracts-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k workflow_access --ui-clients -q --tb=short --maxfail=1 --junitxml=/tmp/unifai-multipurpose-client-final-20261105.xml
```

Source remained frozen during each gate. The native gate precedes one final
cancellation-only exception branch and its two added Mongo cases. The final
eight-case Mongo gate exercises that branch with actual purpose services; the
48-case gate retains ordinary refusal/cancellation/native collision/recovery
contracts. The green Temporal matrix was not repeated for that narrowly scoped
branch. The production-client gate exercises current manual/Session admission
through the extracted API harness. These gates overlap; they are not one
full-platform acceptance run.

Strict mypy passes for the changed execution service and three connected
consent/scheduling/composition modules. Ruff check/format checks cover all seven
affected Python production/test/support files. No UI contract changed. No paid
provider, image build, Kubernetes/OpenShell or broad Temporal matrix was run.
Five diagnostic/test skills validate; eleven changed/reference documentation
files have valid local link targets. `git diff --check` passes. Current status,
plan and evidence index stay within their 100/120/80-line limits.

Final code/test/package manifest:
`/tmp/unifai-multipurpose-final-source-20261105.json`, 1,728 files, SHA-256
`2f77063eb09b1132332896f932137205715340ce431f173c0f1966bcd1ee6cd0`.
Compared with the preceding scheduled-consent manifest, only one production file
and six test/support files changed. Run Engine remains clean at
`60393440efd3876cd6c81e0b013e8bf6d9167659`. Portable formats remain request v9,
Program v5, state/element v3 and scheduled entry/admission v2.

Event ingress investigation found only observation/event-stream ports and generic
runtime waiting, not an authenticated event-to-Program adapter. The next slice
must bind verified source/event identity to approved pinned work and schema-checked
actual inputs without treating portable tags as consent. Variable event inputs
cannot be authorized by blindly reusing a schedule's complete prepared digest.
