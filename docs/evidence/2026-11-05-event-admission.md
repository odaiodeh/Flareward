# Authenticated event admission (2026-11-05)

Generic event-driven root starts now use the canonical Program lifecycle and
submission/provisioning pipeline. This is a backend capability milestone, not
completion of [the full active plan](../plan.md) or the target architecture.

## Implemented behavior

- Human-managed immutable sources pin Program revision, event type, additional
  input contract, scopes, expiry and complete private prepared execution. Creation
  starts no work and provisions no workflow grants. The feature requires explicit
  `UNIFAI_EVENT_SOURCES_ENABLED` and Mongo storage.
- Source keys are purpose-separated, returned once with no-store and persisted
  only as hashes. Owner metadata excludes key/hash/raw prepared configuration.
  Supplied bearers cannot become human authority through cookies; delivery never
  falls back to a cookie. Revocation is one-way and expiry is Mongo-clock-fenced.
- Source/event ID determines the public idempotency key; canonical submission owns
  native identity, claims, provisioning and uncertainty. Concurrent redelivery
  shares one root. Changed concrete inputs conflict, including JSON type changes.
  Receipts expose identifiers/submission only; humans use existing execution views.
- Actual input must satisfy both source and pinned Program schemas. Bundled
  interface validation forbids network schema retrieval. Parser/schema refusals
  hide submitted values and private SDK configuration.
- `ProgramExecutionGateway.bind` is an application-owned snapshot-binding port;
  the Run Engine adapter validates and changes occurrence input/context/identity.
  It preserves compiled placement, resources, nested calls, schema and policies.
  Changed/withdrawn execution configuration refuses new binding. New Program
  revisions cannot retarget an existing source. No second scheduler/executor exists.
- Workflow consent binds the source definition and template digest. Each actual
  occurrence receives original human/time/scopes bound to its concrete request.
  Root provisioning, bounded grants and retirement are unchanged. Event context
  tags carry provenance, not authority. Source revocation blocks new deliveries;
  already admitted roots retain separate cancellation/bounded grant lifecycles.

## Gates and scope

| Gate | Result | Report |
| --- | --- | --- |
| Initial application/lifespan/boundary | 49 passed, 4.15s | `/tmp/unifai-events-initial-contracts-20261105.xml` |
| Actual Mongo source contract/clock/privacy | 2 passed, 0.06s | `/tmp/unifai-events-mongo-20261105.xml` |
| Initial actual Local templates | 3 passed, 1.12s | `/tmp/unifai-events-templates-20261105.xml` |
| Actual signed-cookie HTTP/thread/process | 2 passed, 9.12s | `/tmp/unifai-events-http-20261105.xml` |
| Initial focused Temporal recovery | 1 passed, 8.63s | `/tmp/unifai-events-temporal-20261105.xml` |
| Production event/execution TypeScript clients | 1 passed, 10 deselected, 3.20s | `/tmp/unifai-events-client-20261105.xml` |
| Expanded contract/Local recovery | 73 passed, 4.86s | `/tmp/unifai-events-final-contracts-20261105.xml` |
| Actual private-refusal HTTP | 1 passed, 2.52s | `/tmp/unifai-events-private-errors-20261105.xml` |
| Final contract/Local/template/private parser | 74 passed, 4.81s | `/tmp/unifai-events-final-private-contracts-20261105.xml` |
| Final Temporal/history privacy | 1 passed, 8.30s | `/tmp/unifai-events-temporal-private-20261105.xml` |

These gates overlap; initial/final Temporal rows repeat one scenario with expanded
privacy assertions, not two independent scenarios. All selected runtime gates
passed. Code inspection identified possible raw schema/private-parser diagnostics;
guards and actual refusal tests were added before final verification. Lint format
corrections preceded final checks. No failed runtime gate was silently discarded.

Memory/Mongo share a detached store contract covering typed ownership, bounded
pagination, expiry and idempotent one-way revocation. Mongo also rejects a
DB-expired source despite a slow application clock and refuses inconsistent private
metadata. Application tests use owned ports and canonical `ExecutionService`, not
another test scheduler. They check original approval, namespaced IDs, duplicates,
changed bodies, human/scope/type/schema/expiry/consent refusal and private errors.

Actual HTTP tests publish a graph that requests verification then calls a pinned
Human Review Program. Thread/process operations use two automatically provisioned
purpose credentials. Eight concurrent deliveries create one root and one review.
Wrong credentials/cookies/type/schema are refused; changed payload conflicts.
Source revocation blocks another event but the admitted root still accepts assigned
human review, completes and retires material. Refusal tests check schema, expiry,
unparsed scopes and Program input before any root/grant, without value echo.

The Temporal scenario uses a separate process receiver and worker, starts a pinned
graph/review, stops the worker, then replaces the API at a borrowed listening
socket. Accepted redelivery succeeds while the worker is absent, preserving
original approval/native identity without another grant. A replacement worker
completes review and replays root/child histories. A second event admitted after
restart receives its own root/grant, reaches review, cancels and retires material.
Public native history and process logs contain neither source key nor workflow
credential prefixes. Cleanup addresses only this test's isolated database/runs.

The TypeScript journey creates/inspects/lists a source, concurrently delivers an
event, inspects its completed backend Program through the existing execution
client, conflicts changed input and revokes/refuses retry. No separate UI screen
was added. This does not establish browser authoring/trigger UI acceptance.

## Reproduction and source identity

Use `.venv` and dedicated Mongo27018, Redis6380 database15 and Temporal7234 through
`UNIFAI_TEST_MONGO_URI`, `UNIFAI_TEST_REDIS_URI`, `UNIFAI_TEST_TEMPORAL_ENDPOINT`.

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_event_sources.py -q --tb=short
.venv/bin/python -m pytest multi-agent/tests/integration/http/test_program_events.py -q --tb=short
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_program_events.py -q --tb=short --junitxml=/tmp/unifai-events-temporal-private-20261105.xml
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k program_event --ui-clients -q --tb=short
.venv/bin/python -m pytest multi-agent/tests/application/test_program_events.py multi-agent/tests/application/test_execution.py multi-agent/tests/application/test_workflow_consents.py multi-agent/tests/integration/http/test_lifespan.py multi-agent/tests/integration/run_engine/test_recovery.py multi-agent/tests/integration/run_engine/test_execution_templates.py multi-agent/tests/architecture -q --tb=short --junitxml=/tmp/unifai-events-final-private-contracts-20261105.xml
```

Exercised source stayed frozen during each gate. Later changes sanitized source
and SDK snapshot errors and added history-privacy assertions. The final 74-case
and Temporal gates cover final Python production source. Earlier Mongo/HTTP/client
gates predate those refusal-only changes; persisted data/JSON contracts are unchanged.
The final private HTTP gate checks invalid source/Program inputs. Final strict
mypy passes for all 12 changed production modules; all 20 changed Python files
pass Ruff check/format. UI typecheck passes; subsequent changes were Python-only.
Six diagnostic/test skills validate. Thirteen documentation/reference files have
valid local link targets; compact status/plan/index limits and `git diff --check` pass.

Manifest `/tmp/unifai-events-final-source-20261105.json`: 1,740 code/test/package
files, SHA-256 `6721583939f48cc2a7936dd8cc6177b11e08b8255502cd634ca2714efed3a564`.
Against the preceding admission-recovery snapshot, 23 files changed, including 12
new files; none were removed. Documentation/skills are excluded from that manifest.
Run Engine remains clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.
Request/Program/state/element/schedule-entry formats remain v9/v5/v3/v3/v2.

## Explicit remaining acceptance

Local sources retain the owning Local host and cannot silently recover after its
replacement. Temporal proof does not establish every crash window or isolated
remote delivery. Source creation returns its key once: keyed creation, key
retrieval/rotation/renewal and richer safe settings previews are unfinished.
Generic authenticated delivery is not live Jira/provider signature verification,
event-to-wait routing, tenant traffic/fairness admission or stale-attempt fencing.
No paid provider, new image build, Kubernetes/OpenShell or broad Temporal gate ran.
Verification-plan creation/review in these cases is not trusted Engineering/ADLC
acceptance. Credential rotation, remaining backend control/observation work,
reusable Engineering, unchanged larger delivery composition, unified UI and full
current-image/final requirement audit remain required by the active goal.
