---
name: debug-sharing
description: Diagnose native invitation authorization, concurrent decisions, dependency copying, and sharing UI lifetimes in Lumora.
---

# Diagnose native sharing

Trace the actual request from ui/client/src/api/shares.ts through the FastAPI
adapter into application-owned sharing use cases. Read the
[target architecture](../../../docs/architecture/README.md) and
[active plan](../../../docs/plan.md). Start/resume with
[current status](../../../docs/status.md); read relevant reference sections only.
Native list/details/decline/cancel exist; create/accept/copy remains implementation
work. Missing behavior must become native use cases, not a legacy cloner bridge.

Use lumora.services.sharing.domain.models values and the canonical typed Identity. Scope users and
teams separately, authorize participant roles, and require the selected team scope.
Never authorize from a display name or caller-authored user identity.
Public DTOs omit internal owner pools and private configuration.

Decisions use atomic pending-state transitions: repeated identical outcomes
succeed; conflicting outcomes fail. Copying must validate the full dependency
closure, preserve typed ownership, handle secret references explicitly, and recover
partial failure. Do not certify copy correctness from notification-only tests.

Use canonical UTC timestamps and explicit expiry/retention policy. Check actual
Mongo indexes before adding writers: an invitation-expiry TTL must not erase
accepted audit evidence. Historical string-date and Unicode-alias compatibility
are not requirements for this fresh platform.

Run the relevant tests with [dedicated infrastructure](../run-platform-tests/SKILL.md).
Reuse support/sharing.py and support/share_notification_contracts.py; application
tests use signature-checked ports, adapters use real storage. Check workspace
switches, cancellation of stale refreshes, and actual UI decision submission.
Keep test resources isolated and remove only resources created for the scenario.
