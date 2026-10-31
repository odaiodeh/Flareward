---
name: debug-sharing
description: Diagnose UnifAI native invitation notifications, workspace authorization, legacy date compatibility and concurrent decisions; distinguish these from unfinished share-copy migration.
---

# Diagnose native sharing notifications

Trace the actual `ui/client/src/api/shares.ts` request into
`inbound.http_api.shares` and `mas.application.sharing.notifications`.
Implemented native operations are list, details, decline and cancel. Creation,
acceptance, team copying and cleanup administration still use the legacy sharing
implementation and are not certified on FastAPI. Do not replace missing behavior
with empty fixtures or route the native path through the legacy cloner/bridge.

`mas.domain.sharing` owns invitation/status/direction/item values and sharing
identity comparison. Existing `mas.core.identity` remains the canonical SDK-free
identity value. Importing `mas.sharing` initializes the retained legacy services;
native domain/application imports must avoid that package. Shared invitation
models are used by both paths; there is no second native serialized format.

Authentication resolves the selected `teamId`; the application authorizes the
typed caller against invitation participants. A user whose ID equals a team ID
does not own that team's invitations. Team details and decisions require explicit
team scope; clients carry it as query/body metadata. Display names and authored
user IDs cannot authorize access. Public views preserve flattened sender/recipient
fields for existing clients but omit the internal authorized-owner pool.

Legacy Mongo stores `model_dump(mode="json")`, including ISO date strings and
computed fields. The native reader also accepts BSON datetimes, interpreting naive
Mongo dates as UTC. Sort by converted creation time and stable share ID before
pagination. Do not compare mixed BSON/string values directly. User-ID regexes are
escaped and anchored; recheck domain identity before pagination because Mongo
caseless matching can include distinct Unicode names. Never use a case-insensitive
query for team IDs. A corrupt record must produce a safe storage error, not echo
its document in an HTTP response. This is not a certification of arbitrary Unicode
legacy user-alias discovery; that compatibility boundary remains under review.
Before adding native creation, inspect the existing TTL index: it ignores old
ISO-string expiries but can delete newly written BSON dates. Retention migration
must preserve accepted audit records.

Decline/cancel own role checks and perform an atomic pending-state transition.
Repeated identical outcomes succeed; a competing outcome conflicts. The actual
Mongo shared-contract test races updates. This does not establish safe acceptance
or recovery of the retained legacy clone flow; it still needs a dedicated migration
for ownership, typed dependency closure, private fields and partial failure.

Use [the platform test workflow](../run-platform-tests/SKILL.md) with explicit own
Mongo/Redis URIs. Focused tests:

```sh
.venv/bin/python -m pytest multi-agent/tests/domain/test_sharing.py multi-agent/tests/application/test_share_notifications.py multi-agent/tests/adapters/test_share_notifications.py multi-agent/tests/integration/mongo/test_share_notifications.py multi-agent/tests/integration/redis/test_share_notifications.py multi-agent/tests/architecture -q
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py --ui-clients -q
```

Domain scenarios in `support/sharing.py` import no application/adapter code.
`support/share_notification_contracts.py` runs the same storage behavior against
real memory/Mongo adapters. Application tests use signature-checked port doubles;
signed-cookie tests reuse `support/team_http.py`. The TypeScript `shares` suite
compiles real clients against a separate native API, without mocked MAS responses.

For browser evidence use the full App fixture in
[session UI diagnostics](../debug-session-ui/SKILL.md). Its actual Mongo invitations
are personal and team-specific. Check displayed sender/item, decline, reload,
team scoping and a rapid Alpha-to-Beta switch while Alpha responses are delayed.
`NotificationContext` cancels replaced refreshes and guards mutation callbacks by
workspace lifetime; React completion must not update a replacement workspace.
The fixture has no real recipients and needs no model calls. Close the tab and
owned API/membership processes, then verify removal of only its database, identity
session and team leases. Preserve test services. Rebuild/source-verify both remote
images after installed module or support-fixture changes; a verifier mismatch is
not a test failure to ignore.
