# Managed workflow credentials: in-progress milestone (2026-11-05)

Human-authorized manual/Session admission, recoverable issuance, encrypted-material
retirement, bounded scheduled consent and managed filesystem delivery are implemented.
Event authorization, rotation, broader recovery and isolated remote delivery remain
unfinished. This record does not complete the
[credential milestone](../plan.md#next-milestone-managed-workflow-credential-lifecycle)
or the full platform goal.

## Implemented behavior

The existing review/verification human issuance endpoints accept optional
`Idempotency-Key`. Opt-in configuration requires durable Mongo, an enabled purpose
and a valid Fernet key. Reservations persist original metadata and encrypted
material before atomic purpose registration. Identical retries recover the same
grant/token; different root/scope/TTL/horizon/human conflicts. Authorization is
rechecked, original issuance is fixed and current renewal/revocation wins.

Common domain `WorkflowGrant` removes duplicate lifetime/issuer validation while
purpose scopes remain typed separately. Application-owned store/retirement ports
contain no Mongo/crypto/engine types. Bootstrap wires the store and existing upkeep;
no new scheduler/environment manager exists. Private retirement removes ciphertext
and preserves audit, with an independent database-clock maximum-expiry fence.
The private store rejects plaintext passthrough and malformed cipher values.

Actual API tests exposed verification grant issuance accepting a workflow bearer
alongside a valid human cookie. Shared inbound `HumanPrincipal` now guards review
and verification human-only routes; issuance/list/revoke reject that combination.
Workflow bearer scope and human authority remain separate.

## Gates and scope

| Gate | Result | Recorded report |
| --- | --- | --- |
| Initial application/architecture | 97 passed, 2.98s | `/tmp/unifai-credential-issuance-initial-20261105.xml` |
| Expanded focused application/adapter/native-liveness/lifespan/architecture | 126 passed, 4.26s | `/tmp/unifai-credential-issuance-focused-20261105.xml` |
| Initial actual Mongo/TCP API/native workflows | 23 passed, 1 failed, 47.38s | `/tmp/unifai-credential-issuance-native-20261105.xml` |
| Corrected affected native authorization/restart/review | 11 passed, 34.44s | `/tmp/unifai-credential-issuance-auth-native-20261105.xml` |
| Final HTTP lifespan/architecture | 17 passed, 3.79s | `/tmp/unifai-credential-issuance-contract-final-20261105.xml` |
| Final production TypeScript Human Review client | 1 passed, 6 deselected, 3.03s | `/tmp/unifai-credential-issuance-client-final-20261105.xml` |
| Final Mongo material scenarios | 8 passed, 0.39s | `/tmp/unifai-credential-issuance-mongo-final-20261105.xml` |

These gates overlap. The initial native failure was verification bearer-plus-cookie
issuance returning 201 instead of 401; the correction retained the refusal assertion.
The 126-case gate precedes that HTTP correction. The corrected 11 cases cover both
purpose restart journeys, scope-only verification HTTP and graph/backend review on
thread/process runners. The subsequent narrow HttpServices/library composition
checks were covered by final lifespan/architecture and client checks. Application,
grant storage and crypto code remained unchanged after the expanded focused gate.
The unchanged passing Mongo cases were not blindly rerun after the HTTP correction.
The final Mongo gate adds two test-only cases proving an actually expired maximum
horizon removes ciphertext despite unavailable native authority, while preserving
live material. Production code did not change for that addition.

Mongo proves concurrent reservation/registration, same-token renewal preservation,
revocation, ciphertext removal with audit retained, fast-clock expiry refusal and
plaintext/ciphertext refusal. Signed-cookie TCP API journeys restart before root
admission, recover the grant, start a real native Wait root, authenticate the bearer,
cancel/drain that root and observe material retirement. Human listing/revocation
works while bearer-plus-cookie management is denied. No live provider was called.

## Reproduction

From the repository root, use the existing Python 3.14 `.venv`. Native commands
require dedicated `UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018` and
`UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15`.

```sh
.venv/bin/python -m pytest multi-agent/tests/application/test_credential_issuance.py multi-agent/tests/application/test_credential_renewals.py multi-agent/tests/application/test_reviews.py multi-agent/tests/application/test_review_program.py multi-agent/tests/application/test_verification_access.py multi-agent/tests/application/test_execution_grant_access.py multi-agent/tests/adapters/test_verification_settings.py multi-agent/tests/integration/run_engine/test_workflow_access_lifetime.py multi-agent/tests/integration/http/test_lifespan.py multi-agent/tests/architecture -q --tb=short --junitxml=/tmp/unifai-credential-issuance-focused-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_credential_issuance.py multi-agent/tests/integration/http/test_credential_issuance.py multi-agent/tests/integration/mongo/test_credential_renewals.py multi-agent/tests/integration/mongo/test_credential_retirement.py multi-agent/tests/integration/reviews/test_credential_renewal.py multi-agent/tests/integration/reviews/test_workflow.py::test_native_workflow_resumes_only_from_the_assigned_human_decision multi-agent/tests/integration/http/test_verification_access.py -q --tb=short --junitxml=/tmp/unifai-credential-issuance-native-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/http/test_credential_issuance.py multi-agent/tests/integration/http/test_verification_access.py multi-agent/tests/integration/reviews/test_workflow.py::test_native_workflow_resumes_only_from_the_assigned_human_decision -q --tb=short --junitxml=/tmp/unifai-credential-issuance-auth-native-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/http/test_lifespan.py multi-agent/tests/architecture -q --tb=short --junitxml=/tmp/unifai-credential-issuance-contract-final-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k human_review --ui-clients -q --tb=short --junitxml=/tmp/unifai-credential-issuance-client-final-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_credential_issuance.py -q --tb=short --junitxml=/tmp/unifai-credential-issuance-mongo-final-20261105.xml
```

Strict mypy passes for 15 affected production modules using
`MYPYPATH=multi-agent/lib:multi-agent/adapters:multi-agent/plugins:multi-agent`,
`--strict --follow-imports=silent`. Affected production/test/support Ruff checks,
diagnostic skill validators and `git diff --check` pass.

## Snapshot and remaining acceptance

Earlier issuance source manifest: `/tmp/unifai-credential-issuance-source-20261105.json`, 1,705 code/
test/package files; aggregate SHA-256
`aff81d2830c512bca9be7a411c116e2ab5d92731ef541da6e29511e1484ba78f`.
The preceding final-code snapshot before those two test-only cases is retained at
`/tmp/unifai-credential-issuance-before-expiry-cases-20261105.json`, SHA-256
`5216d02fd5dc74b68a03251d7775c60606175fb7c732529f73c54aab2edb7405`.
Prepared/Program/state/element formats remain request v9, Program v5, state v3,
element v3. Run Engine is unchanged at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

The earlier snapshot predates managed delivery below. Its passing gates do not
cover later production changes; the following gates cover the delivery snapshot.

## Managed trusted-filesystem delivery and recovery

`CredentialDelivery` and `WorkflowCredentialSource` are narrow application ports.
Bootstrap wires private file delivery into recoverable keyed issuance and normal
receiver build contexts; review/verification plugins use their normal factories.
Receiver resolution needs no vault key. A configured source failure cannot fall
back to an operator file. No token/directory binding enters portable execution data.

The absolute-directory adapter enforces owner/root/purpose isolation, current-user
ownership, private modes, no-follow bounded reads, immutable concurrent slot writes
and refusal of ambiguous active grants. File retirement retains token-free markers
that reject a delayed producer. Mongo ciphertext retirement atomically creates
`cleanup_pending`; file removal and acknowledgement are separately retryable.
Unknown destinations remain pending rather than deleting a different directory.
The existing upkeep owns this work; no scheduler/environment manager was added.

| Gate | Result | Recorded report |
| --- | --- | --- |
| Initial file/application/architecture | 84 passed, 3.32s | `/tmp/unifai-managed-delivery-initial-20261105.xml` |
| Final file/configuration/application/lifespan/architecture | 114 passed, 4.61s | `/tmp/unifai-managed-delivery-focused-20261105.xml` |
| Actual Mongo/TCP API/native review and verification | 36 passed, 93.16s | `/tmp/unifai-managed-delivery-native-20261105.xml` |
| Production TypeScript Human Review client with managed delivery | 1 passed, 6 deselected, 3.21s | `/tmp/unifai-managed-delivery-client-20261105.xml` |
| Concurrent roots sharing one managed directory | 2 passed, 8.86s | `/tmp/unifai-managed-delivery-isolation-20261105.xml` |
| Initial unavailable-source regression | 2 failed, 10 deselected, 0.15s | `/tmp/unifai-managed-delivery-source-failure-initial-20261105.xml` |
| Corrected source translation/file/application/architecture | 86 passed, 3.31s | `/tmp/unifai-managed-delivery-source-failure-final-20261105.xml` |

The native gate contains 10 actual Mongo cases, two signed-cookie API restart/
native-cancellation cases, 16 graph/backend review approval/rejection cases and
eight graph/reusable-verification-waiter cases. Workflow cases cover thread/process
and both managed and explicit operator bindings. Managed cases write no test token
file and observe ciphertext retirement, acknowledged collection and empty token
directories. The client uses the same production API/native receiver path.

Mongo recovery injects a collection failure, then reconstructs the store, delivery
adapter and controller against persisted state: ciphertext is already absent,
outbox cleanup completes, audit remains and captured stale delivery is refused.
The filesystem contract separately covers lost cleanup acknowledgement. This is
controller reconstruction/fault injection, not an actual killed-worker proof.

Two simultaneous native roots use the same managed directory on thread/process
receivers. Cancelling one collects only its material and denies its bearer, while
the other retains authority, receives human approval and completes. Cross-root
review access is refused; final cleanup drains both. No grant-service liveness
double is substituted in these native tests.

The unavailable-source regression reproduced both gateways leaking a generic
material exception instead of a retryable infrastructure failure. The shared
source port now owns `WorkflowCredentialUnavailable`; purpose HTTP gateways
translate it to their application-owned unavailable error. The actual receiver
error translator preserves retryability and private diagnostics. Both regression
cases pass inside the final 86-case focused gate.

Reproduce the 36-case gate with the dedicated Mongo/Redis variables above:

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_credential_issuance.py multi-agent/tests/integration/http/test_credential_issuance.py multi-agent/tests/integration/reviews/test_workflow.py::test_native_workflow_resumes_only_from_the_assigned_human_decision multi-agent/tests/integration/verification/test_workflow.py::test_graph_and_reusable_waiter_use_root_scoped_access_without_evidence_authority -q --tb=short --junitxml=/tmp/unifai-managed-delivery-native-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/adapters/test_workflow_credential_delivery.py multi-agent/tests/adapters/test_receiver_secrets.py multi-agent/tests/adapters/test_verification_settings.py multi-agent/tests/application/test_credential_issuance.py multi-agent/tests/application/test_credential_renewals.py multi-agent/tests/integration/http/test_lifespan.py multi-agent/tests/architecture -q --tb=short --junitxml=/tmp/unifai-managed-delivery-focused-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k human_review --ui-clients -q --tb=short --junitxml=/tmp/unifai-managed-delivery-client-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/reviews/test_workflow.py::test_managed_roots_share_delivery_without_sharing_authority_or_cleanup -q --tb=short --junitxml=/tmp/unifai-managed-delivery-isolation-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/adapters/test_workflow_credential_delivery.py multi-agent/tests/application/test_credential_issuance.py multi-agent/tests/application/test_credential_renewals.py multi-agent/tests/architecture -q --tb=short --junitxml=/tmp/unifai-managed-delivery-source-failure-final-20261105.xml
```

Strict mypy passes for 13 affected production modules with the MYPYPATH/options
above. Ruff passes for affected production/test/support files. Source remained
frozen throughout each gate. The client test switch and new isolation test were
exercised separately. Four later production edits add the shared source exception,
make material unavailability its subtype and translate it in both gateways. The
final 86 cases and repeated strict typing cover that correction. The earlier
36-case positive/native and client gates precede it; they were not broadly rerun
for the exception-only correction. These gates do not constitute final platform
regression or current-image acceptance.

Delivery source manifest: `/tmp/unifai-managed-delivery-source-20261105.json`,
1,707 code/test/package files; aggregate SHA-256
`c6c2c18f125d6e10ef62f05dbf2101b536deb42f9339ce0468b9381316f4d2bd`.
Final correction/test manifest:
`/tmp/unifai-managed-delivery-final-source-20261105.json`, 1,707 files, SHA-256
`477acd763003ee97fb7850983a2f39938c4e4ce79de9369391700a2ac9606a2a`.
Run Engine HEAD/clean status was rechecked unchanged at the baseline above.
Public execution formats remain request v9/Program v5/state v3/element v3.

At the delivery snapshot, API restart proof was pre-provisioning, not restart of a running Local
root. Human keyed issuance still precedes dispatch; automatic manual/Session/
scheduled/event admission requires explicit authority, frozen scope and approval
provenance. Rotation, per-node least privilege, hostile-code isolation, isolated
remote delivery, current-image Kubernetes/OpenShell, worker loss/replay and full
platform acceptance remain open. Do not expose the all-root directory or vault
key to a sandbox. Explicit operator files/provider credentials remain uncollected;
token-free fences and audit persist. No paid provider, image build or broad
remote/Temporal gate ran for this increment.

## Human-authorized manual and Session admission

Canonical execution/Session requests accept explicit, secret-free `workflow_access`.
Installed purpose services own scope/action/policy validation. A human-only HTTP
guard rejects bearer-plus-cookie elevation. The application freezes approval of
the exact owner/root/request before durable admission; Session staging persists
it before reconciliation. Portable credential-user tags cannot approve capabilities.

The existing submission claim provisions through a narrow application port before
native dispatch, using recoverable purpose issuance and the existing managed source.
Uncertain provisioning recovers the original approval/key. Cancellation during
provisioning prevents dispatch; root completion retires authority/material. No new
scheduler, execution registry, environment manager or credential-returning API exists.
Credential-root authority now reads records/native status through read-only ports,
without a dependency on the submission service.

| Gate | Result | Recorded report |
| --- | --- | --- |
| Initial execution/authority/issuance/renewal/architecture | 104 passed, 3.50s | `/tmp/unifai-workflow-admission-initial-20261105.xml` |
| Initial actual admission/liveness | 8 passed, 4 failed, 109.06s | `/tmp/unifai-workflow-admission-native-initial-20261105.xml` |
| Corrected actual admission and existing Session journeys | 15 passed, 26.63s | `/tmp/unifai-workflow-admission-native-final-20261105.xml` |
| Final focused application/Session/lifespan/boundary | 117 passed, 4.89s | `/tmp/unifai-workflow-admission-focused-20261105.xml` |
| Production manual/Session TypeScript clients | 2 passed, 7 deselected, 10.17s | `/tmp/unifai-workflow-admission-client-20261105.xml` |

The initial native gate exposed an incorrect removal of general `is_active`, still
used by the review adapter for exact root/child checks. Owned API logs identified
that AttributeError. The general method is restored; root credential checks remain
independent. Assertions/timeouts were not relaxed to hide the regression.

The corrected native gate includes eight purpose × manual/Session × thread/process
admission cases, six existing native Session cases and one native Session HTTP
journey. New cases begin with zero grants, reject bearer elevation and malformed
private-looking scope input without echoing it, execute real receivers, approve
review as the assigned human, retry the same intent, and observe one retired,
acknowledged material row and empty managed token files. They never call the grant
issuance endpoint or write a token file. Verification creation is not a claim of
accepted candidate work. Native APIs use real Mongo/Redis; authority doubles are
confined to application tests. Optional Claude/DeepAgent discovery warnings in
API logs reflect absent optional packages, not skipped selected backends.

Application cases cover missing human authority despite portable user tags,
recoverable provisioning, fixed request/approval binding, scope-widening refusal
and cancellation before dispatch. The client gate invokes the production manual
and canonical Session clients, then the assigned-reviewer client, and inspects the
same frozen approval and completed native execution without receiving tokens.

Reproduce with the dedicated Mongo/Redis variables documented above:

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/http/test_workflow_admission.py multi-agent/tests/integration/run_engine/test_sessions.py multi-agent/tests/integration/http/test_sessions.py -q --tb=short --junitxml=/tmp/unifai-workflow-admission-native-final-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/application/test_execution.py multi-agent/tests/application/test_execution_grant_access.py multi-agent/tests/application/test_credential_issuance.py multi-agent/tests/application/test_credential_renewals.py multi-agent/tests/application/test_session_approval_rules.py multi-agent/tests/adapters/test_memory_sessions.py multi-agent/tests/integration/http/test_lifespan.py multi-agent/tests/integration/run_engine/test_scheduled_admission.py multi-agent/tests/architecture -q --tb=short --junitxml=/tmp/unifai-workflow-admission-focused-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k workflow_access --ui-clients -q --tb=short --junitxml=/tmp/unifai-workflow-admission-client-20261105.xml
```

Strict mypy passes for 15 affected production modules; Ruff and `npm run typecheck`
pass. Each gate used frozen exercised source. Subsequent source edits only narrow
authority port/TypeScript actor annotations and wrap one unchanged string literal;
strict typing was repeated after the Python changes. They add no runtime behavior.
Full regression/required remote gates remain outstanding.

Source manifest: `/tmp/unifai-workflow-admission-source-20261105.json`, 1,712 files,
SHA-256 `b47f2de0395478d273c87ac6b0d513b0db3ed0975df49016099d73970339dfa4`.
The four updated diagnostic/test skills validate; local documentation targets and
`git diff --check` pass. Final source formatting does not change runtime behavior.
Prepared/Program/state/element formats remain request v9/Program v5/state v3/element v3;
approval is application record data, not a native worker payload.

Scheduled/event consent, multi-purpose partial-admission/concurrent native proof,
automatic rotation, isolated remote delivery, API/worker recovery/replay and
full UI controls remain open. Earlier pre-provisioning API restart does not prove
the new automatic admission survives a running-root restart. No paid provider,
image build, broad Temporal/replay or Kubernetes/OpenShell gate ran for that slice.

## Recurring source consent and trusted tick admission

Schedule configuration can request bounded workflow scopes under authenticated
human consent. Private Mongo metadata binds owner/actor/time, expiry (at most 30
days), exact definition/version and prepared digest. Only an opaque ID enters the
native registration. A tick compares the currently applied registration, resolves
live private consent with a Mongo-clock expiry fence and uses the common purpose
provisioning port. Failed/superseded update metadata cannot authorize another
registration. Revocation blocks future API/native admission; existing admitted
roots keep their independent bounded grants and cancellation commands.

`WorkflowAccessComponents`/settings now compose API and trusted-worker authority
once. Read-only native observation borrows the public SDK RPC facade. Calendar
list/detail metadata is consistent, and owner-authorized deletion remains possible
if optional consent metadata is unavailable. Canonical request identity also
rejects boolean/integer/float substitutions instead of relying on Python equality.

| Gate | Result | Recorded report |
| --- | --- | --- |
| Initial schedule/configuration/architecture | 32 passed, 3.99s | `/tmp/unifai-scheduled-consent-initial-20261105.xml` |
| Consent/execution/issuance/settings/boundary | 101 passed, 3.73s | `/tmp/unifai-scheduled-consent-focused-20261105.xml` |
| Actual Mongo and manual/Session regression | 9 passed, 25.74s | `/tmp/unifai-scheduled-consent-local-native-20261105.xml` |
| Initial focused Temporal gate | 1 failed; two unreached, 33.56s | `/tmp/unifai-scheduled-consent-temporal-20261105.xml` |
| Corrected Temporal worker/replay/calendar gate | 3 passed, 21.96s | `/tmp/unifai-scheduled-consent-temporal-corrected-20261105.xml` |
| Coordinator-resolution regression | 1 passed, 0.57s | `/tmp/unifai-program-resolution-coordinator-20261105.xml` |
| Final consent/program-model/lifespan/boundary | 49 passed, 4.43s | `/tmp/unifai-scheduled-consent-final-contract-20261105.xml` |
| Final production schedule clients | 1 passed, 9 deselected, 3.19s | `/tmp/unifai-scheduled-consent-client-final-20261105.xml` |
| Final exact JSON request identity/consent | 14 passed, 0.15s | `/tmp/unifai-scheduled-consent-identity-final-20261105.xml` |

The first Temporal test reached successful tick admission but its backend Program
failed before opening review: installed declaration resolution used
`asyncio.to_thread`, unsupported by the workflow coordinator loop. The owned public
native history/outcome identified `NotImplementedError`; the activity completed.
Declarations are now resolved synchronously after preload, while I/O stays behind
invocation ports. A coordinator-executor refusal test and actual replay cover the
fix. Raw Temporal completion can contain a failed engine envelope; assertions use
the SDK's operational status. The initial gate stopped on its first failure;
the corrected run exercised all three selected cases without relaxed timeouts.

The two new Temporal cases use actual signed-cookie API/Mongo/Redis, a separate
worker, and thread/process review operations. They start with zero workflow grants,
trigger the owning calendar root, restart its worker during pending review, accept
the assigned human decision, complete/replay that root and observe material cleanup.
They then revoke consent and force a direct native tick: operational failure occurs
before a second grant/review is created. This is worker restart during review;
the concurrent response task is not proof that its decision committed while the
worker was absent. The third case retains composed schedule execution, API restart
and replay without access requirements. Each test deletes only its owned calendar
and drains owned running actions. Optional missing-provider discovery warnings
remain scoped to absent Claude/DeepAgent packages; no paid model was called.

Reproduction uses dedicated Mongo27018/Redis6380 database15/Temporal7234 variables:

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_scheduled_workflow_access.py 'multi-agent/tests/integration/deployment/test_schedules.py::test_scheduled_program_runs_in_owning_engine_run_across_api_restart[composed]' -q --tb=short --maxfail=1 --junitxml=/tmp/unifai-scheduled-consent-temporal-corrected-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k schedule_consent --ui-clients -q --tb=short --junitxml=/tmp/unifai-scheduled-consent-client-final-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/application/test_program_schedules.py multi-agent/tests/application/test_workflow_consents.py -q --tb=short --junitxml=/tmp/unifai-scheduled-consent-identity-final-20261105.xml
```

Strict mypy passes for 19 affected modules; Ruff formatting/lint and UI typecheck
pass. Source stayed frozen during gates. The later list/detail/deletion changes
were covered by the final 49-case/client gates; the last canonical-identity change
was covered by the 14-case gate. The green Temporal matrix was not broadly rerun
for those API-only changes. These records overlap and are not one aggregate gate.

Final source manifest: `/tmp/unifai-scheduled-consent-final-source-20261105.json`,
1,725 code/test/package files, SHA-256
`44b9363f348b043eb3b8fd97aeafdb0c7d514158e63377390e1b1992fb9ff274`.
Run Engine remains clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.
Prepared/Program/state/element formats remain v9/v5/v3/v3; scheduled entry/admission
contracts are v2. No images, Kubernetes/OpenShell or broad Temporal gates ran.
Event ingress, multi-purpose concurrency/partial issuance, running-root API
restart with automatic access, other purposes, rotation, isolated remote delivery,
refused-admission UI views and final platform acceptance remain open.
