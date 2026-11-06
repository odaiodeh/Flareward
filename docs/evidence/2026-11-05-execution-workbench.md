# Pinned invocation and shared execution/review workbench

Recorded 2026-11-05. This advances the thin product journey. It does not establish
full Engineering UI/live-agent acceptance or complete workspace convergence.

## Implemented boundaries and behavior

- `ProgramInvocation` loads the selected immutable revision's schema. Structured
  inputs and JSON editing share one input value; invalid JSON blocks submission
  and view switching. Draft changes cannot change the selected revision's form or
  execution configuration. Uncertain delivery preserves the same intent and input.
  A definite 422 enables correction under the same execution ID; normal admission
  identity checks still prevent replacement of accepted work.
- Accepted starts navigate to `/executions/:id`. The shared owner-scoped workbench
  reads persisted execution/child snapshots and shows phase/submission, actual
  root/parent/child/session relationships, cancellation, inputs/results and reviews.
  Read failure remains unavailable, with any cached data labeled last-observed.
  No artificial progress, completion or verification claim is synthesized.
- The embedded `ProgramRun` was removed. Session stream hooks retain the exact
  observed session/root reference and link to the same route only when it matches
  the selected session. Shared/public chat does not promise owner-only inspection.
- Inbox and workbench reuse `ReviewDetail`, preserving exact occurrence/revision,
  immutable decision intent and uncertainty handling. Configuration, invocation
  and response forms use shared schema fields. The old scalar-only review renderer
  and its detection helper were removed. Root defaults are copied; required scalar
  values remain unset for the user.
- `ReviewService.for_execution` owns owner/root review inspection through a narrow
  repository port. The HTTP adapter requires a human principal, including rejecting
  bearer-plus-cookie requests. Owner inspection does not grant reviewer assignment.
  Mongo uses an indexed owner-type/id/root query, query-scoped cursor and validated
  projections; the application rechecks returned owner/root identities.
- Query contracts are shared between memory and Mongo. Technology details remain
  in the adapter. Stored documents now require matching owner/root projections;
  no old-format compatibility reader or automatic data migration was introduced.

The UI does not add a scheduler, native waiting mechanism or credential resolver.
Review creation/wait/continuation still use the existing application and Run Engine.

## Verification gates

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**718 passed in 6.53s**, no skips or reported warnings. This is the stated shared
scope, not 718 new tests and not the earlier adapter-inclusive 732-test gate.

Using UnifAI's dedicated Mongo/Redis:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/mongo/test_review_queries.py \
  multi-agent/tests/integration/reviews/test_workflow.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**25 passed in 69.68s**, no skips or reported warnings. Covers shared owner/root/
cursor isolation, projection tampering refusal and existing native thread/process
review outcomes, authorization and lifecycle scenarios, now including root queries.

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/ui/test_editor_client.py::test_human_review_typescript_clients_resume_a_native_workflow \
  --ui-clients -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

Final **1 passed in 5.29s**, no skips or reported warnings. Actual production clients
prove reviewer inbox access, owner-only root listing, pagination, different-root
isolation, exact response retry/conflict and native continuation. This is transport/
workflow evidence, distinct from React browser evidence below.

Strict mypy passes for the four changed production Python modules with
`MYPYPATH=multi-agent/lib:multi-agent/adapters:multi-agent/plugins:multi-agent` and
`--strict --follow-imports=silent`. All 14 changed Python source/test files pass
Ruff check/format. Updated composition/review/session skills validate.

From `ui/`, `npm run typecheck`, `node tests/run-api-contracts.mjs contracts` and
`NODE_ENV=production node tests/build-placement-browser.mjs /tmp/unifai-execution-workbench-browser`
pass after the final code changes. Contracts include shared initial-value/default
copy semantics and existing schema/graph/session behavior. Final build **4.61s**;
the existing circular vendor chunk and large-chunk warnings remain.

## Actual App browser journeys

Used the maintained signed-cookie `support.program_browser` and
`support.review_browser` runners with dedicated Mongo/Redis and the actual App,
providers, production clients and native execution. External identity/settings,
test Programs/operations and the review subject are controlled peers. No live
model, paid provider or trusted software verification is represented by this proof.

### Published inputs and correction

Created `typed_program` with Multiplier 2 and published revision 1. Saved draft
version 2 with Multiplier 3 and input title `Draft-only label`. Invocation still
rendered the published `Label` field and no draft-only field. Array add/remove and
JSON view switching worked; malformed JSON refused switching and remained visible.
Submitted amount 3, label `published-input`, tags `["retained"]`. The shared execution
route reported completed and returned total **6**, proving revision 1 behavior.
Execution: `9f10a7af-586f-42a4-87d7-785b601ec905`.

A later valid-JSON but invalid-contract `{}` request received 422. Inputs became
editable and the displayed submission link retained
`a03fa123-b72a-426d-afa1-f8b99f55393f`. Correcting the request to amount 2/label
`corrected` and retrying opened that same execution URL and returned total **4**.
No new execution identity was substituted for correction.

### Cancellation and nested review

Published `waiting`, invoked it, requested cancellation in the shared workbench and
observed **cancelled**, not an assumed terminal result. Reloading the same URL
preserved cancellation. Execution: `a694621c-2a27-4d49-8f2c-2c4055ca3b6a`.

The review fixture opened an actual graph root and review child. As owner, the
workbench showed the exact pending subject and no Approve button. Clicking the
observed child opened its actual execution, with root/parent links. The assigned
reviewer used the inbox's shared detail component to approve. Returning through the
owner login showed root/child completed and the persisted reviewer decision.

After consolidating response forms, repeated approval with the final shared schema
renderer and final built assets. Root `30676817b6b9484f8fa7faf2c8791b32` completed;
review `746d03b26499d83cb776fda8f6153593dedd4b9940a182934b04ed1224e25dc3`
retained feedback `Final shared schema form review.` and reviewer identity.
The [final screenshot](assets/2026-11-05-execution-workbench.jpg) records this view.

Pinned-input/cancellation proof used earlier incremental builds of unchanged
workbench behavior; correction used the subsequent rejection-handling build.
The final review/schema build and all final static gates followed consolidation and
initial-value helper extraction. No full Session browser journey was exercised.

## Cleanup, diagnostics and limitations

All owned tabs and API/identity processes were closed. Each final log confirms
`Application shutdown complete`. Runners confirmed removal of their own databases,
including `unifai_program_browser_03bf80a2f1fe4665ab56464053df4da6` and
`unifai_review_browser_25ef091f6a6c49f585361a012d7842f8`. Private cookie/root files
and owned sessions use fixture cleanup; shared infrastructure was retained.

An initial Program fixture started before the build directory existed and failed;
its owned state was cleaned. The successful run started after assets were ready.
The review fixture reported unavailable optional Claude/deep-agent SDKs during
reflective discovery. They were not used. Fixture administration access checks and
favicon requests returned 404; the Program fixture deliberately disables reviews
and its workbench truthfully displayed review-service 503/unavailability. These are
not evidence of administration, optional-provider or all-deployment acceptance.

Immediate child transport remains unpaginated. Operation occurrences, attempts,
resumable timeline/live flow, artifact/report inspection, safe capability-consent
authoring, full Engineering/Session browser acceptance and canvas convergence remain
open. Cross-owner reviewers can inspect their assigned review; full owner execution
inspection still requires owner authority. Unconfirmed invocation intents currently
survive only the mounted form, not browser reload. The UI does not yet request the
managed capabilities needed to start the complete Engineering flow.

No remote images, Kubernetes/OpenShell/Temporal matrices, live coding or production
verifier acceptance was attempted. Those remain required at their planned milestones.

## Source identity

[The focused manifest](2026-11-05-execution-workbench-source.json) records 35 source
files, two removed paths, the final screenshot and built workspace script. Source
aggregate SHA-256:
`b123d9cdfac93b16fbcfc0e8d397097b0f2e386234d6073bb2a72bf5ac8c6fe1`.
This is not a complete dependency/image manifest or proof of universal compliance.
The broader target and deferred acceptance requirements remain active.
