---
name: debug-program-events
description: Diagnose UnifAI event-source authority, frozen Program templates, duplicate delivery, private errors and native restart/replay.
---

# Diagnose Program event starts

Read [current status](../../../docs/status.md), [the active plan](../../../docs/plan.md)
and the relevant [event contract](../../../docs/program-platform-development.md#authenticated-event-driven-program-starts).
Use the [evidence index](../../../docs/evidence/README.md) for the selected proof;
do not load entire guides or archives. This is root admission through the existing
execution service, not another scheduler or environment lifecycle.

- `UNIFAI_EVENT_SOURCES_ENABLED` requires Mongo. Humans create/list/inspect/revoke
  immutable, bounded sources. A source pins its Program and complete private
  preparation; new drafts/resources must not retarget it.
- Creation returns a purpose-separated source key once. Only its hash persists.
  Metadata/receipts contain no key or raw preparation. A lost creation response
  requires inspecting/revoking the unusable source and explicit replacement; no
  current keyed-creation/rotation/retrieval contract exists.
- A supplied bearer cannot become human authority through a cookie. Delivery
  accepts only its source bearer, regardless of cookies. Unknown, wrong, expired
  or revoked keys refuse admission; private-store failure is unavailable, not an
  authentication fallback. Mongo's clock fences expiry even with a slow API clock.
- Source/event ID identifies one root; changed input must conflict, including
  boolean/integer/float substitutions. The normal submission claim handles
  concurrent starts and uncertain delivery under its own private native ID.
  HTTP 202 is an admission receipt, not completed or accepted work.
- Additional source schemas and the pinned Program schema both apply. Reuse
  bundled interface validation. Do not echo submitted values or SDK preparation
  data in parser errors. The event context tag is provenance, never authority.
- Scope consent matches the private source definition and frozen template digest.
  Bind the original human/time to each actual request through the shared workflow
  provisioning port. Do not reuse a calendar tick's concrete-request digest for
  variable event inputs, infer consent from tags, or put source/workflow keys into
  definitions, inputs, payloads or logs.
- `RunEngineGateway.bind` changes occurrence input/context/native identity only.
  Native context rebinding supplies graph/child invocation identity; hand-editing
  embedded child contexts can break ownership. Changed/withdrawn profiles or work
  budget policy refuse new bindings. Do not silently recompile approved work.
- Local sources pin the owning in-memory host and cannot silently recover on a
  replacement host. Durable API/worker recovery uses Temporal with the original
  location. Preserve its actual root/child history and replay; never start a new
  root because observation timed out.
- Revoking a source prevents future deliveries, including retries. Already admitted
  roots retain their bounded grants and explicit cancellation. This is not an
  atomic fence on external effects already in flight or a tenant rate limiter.

Use `support/event_sources.py` for the shared Memory/Mongo store contract;
`application/test_program_events.py` for approval/refusal and canonical admission;
`integration/run_engine/test_execution_templates.py` for actual frozen graph
binding and policy/ownership refusal. `integration/http/test_program_events.py`
uses actual API/Mongo/Redis, both purposes and thread/process nested review.
`deployment/test_program_events.py` covers accepted redelivery without a worker,
API/worker replacement, new occurrences, replay and private history/cleanup.
The production TypeScript clients run via the `program_event` UI-client case.

Use dedicated service URIs and the milestone cadence in
[the test skill](../run-platform-tests/SKILL.md). Generic authenticated delivery
does not prove live provider signature verification, event-to-wait routing,
source-key rotation, remote sandbox delivery or full ADLC completion.
