# Managed artifact capabilities: trusted Local checkpoint

The interrupted artifact workflow service is integrated with normal admission,
encrypted material reservation, private receiver delivery, capped renewal, persisted
revocation/expiry and the shared terminal cleanup outbox. No parallel scheduler,
environment manager or credential store was added. Application policy/ports remain
inside; Mongo, HTTP, private-file transport and wiring remain outside.

`artifact@1` scopes an owner/root, read/publication actions, namespaces/blob IDs,
per-transfer bytes and lease/horizon. Mongo uses the shared lifecycle CAS and both
API/database clocks. Authentication requires an active root and a second grant read;
this does not atomically fence effects admitted before cancellation/revocation.
An operator byte-limit reduction refuses broader credentials and maintenance revokes
their grants. Original reservation identity survives uncertain registration; changed
root/scope retries fail. Closed roots and expired/revoked grants cannot be revived.

Enable `UNIFAI_ARTIFACT_WORKFLOW_ENABLED` with artifact storage, durable Mongo,
recoverable issuance/key and managed delivery configuration. The scheduled admission
worker shares purpose settings; artifact-only recoverable deployments are permitted.
The ordinary provider factory receives the existing credential-source port and
resolves only its owner/root. Source failure cannot fall back to an operator file.
The gateway validates owner/root before transferring and disables HTTP redirects
and environment proxy discovery. Manual operator bindings remain a distinct feature;
their file reader now rejects symlinks, nonregular/public/foreign-owned files,
oversized/empty/invalid bindings. Human grant management rejects any bearer even
alongside an otherwise valid human session.

The existing Local Engineering journey requests artifact/review/verification access
through normal submission. It has no manual artifact issuance or token file. The
same published revision runs standalone and within the deterministic delivery graph,
checks exact stored bytes and repair identity, accepts an authenticated test-human
decision, downloads the artifact after workspace deletion, and observes retirement
of every purpose's material plus artifact grant revocation. Public root responses
and API logs are checked for purpose-token prefixes. This is not a forensic audit
of every history/log/store.

## Final checks

From the repository root:

```sh
.venv/bin/python -m pytest multi-agent/tests/adapters/test_artifact_credentials.py multi-agent/tests/integration/http/test_artifact_access.py multi-agent/tests/adapters/test_verification_settings.py multi-agent/tests/application/test_artifact_workflow_access.py multi-agent/tests/application/test_engineering_program.py multi-agent/tests/application/test_credential_issuance.py multi-agent/tests/application/test_credential_renewals.py multi-agent/tests/architecture -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_artifact_workflow_access.py multi-agent/tests/integration/verification/test_engineering_workflow.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

The final focused gate passed 117 tests in 4.04s. The final native gate passed
four tests in 22.50s: Mongo lifecycle/database-clock fencing and Engineering Local
thread/process journeys. No cases were skipped. The first native attempt produced
four setup errors because the sandbox denied localhost sockets; the authorized
networked run passed. Test-development failures involved a mock issuer, an omitted
test root identity and disabled-service authentication prerequisites; those fixtures
were corrected. The human bearer-plus-session guard was tightened before the final
gates; an earlier native pass does not substitute for that final run.

From `multi-agent`, strict typing passed for all 11 changed production modules:

```sh
MYPYPATH=lib:adapters:plugins:. ../.venv/bin/mypy --strict --follow-imports=silent lib/mas/application/artifacts/workflow_access.py lib/mas/application/artifacts/access_models.py adapters/outbound/mongo/artifact_workflow_access.py bootstrap/workflow_access.py bootstrap/platform.py config/platform_settings.py config/workflow_access_settings.py adapters/inbound/http_api/dependencies.py adapters/inbound/http_api/artifact_access.py plugins/mas_plugins/artifacts/specification.py plugins/mas_plugins/artifacts/http.py
```

An initial invocation without the source-root paths failed import discovery; the
command above is the actual final typing proof. Ruff lint and format checks passed
on the 17 source/test files in the [source manifest](2026-11-05-managed-artifacts-source.json).
Its aggregate SHA-256 is
`489bddc61b6f2bd6bf279a124f2716901385931685d9d0af896113d5e3534868`,
computed over the sorted compact JSON path-to-hash map. This is a focused checkpoint,
not a full-source/remote-image manifest. Source was frozen during the final gates.

## Remaining acceptance

Engineering's candidate files are still test-created; check/Jira/CI/deployment peers
are deterministic and make no paid calls. Production coding-operation artifact
generation in Engineering, API/worker restart and replay for this new purpose,
scheduled/event-purpose recovery, remote delivery/isolation and adverse cleanup
remain unproven. Existing shared lifecycle evidence does not automatically prove
these new-purpose combinations. Full root credential rotation, tenant fairness,
stale-attempt effect fencing and load acceptance remain open.

No Docker build, Temporal or Kubernetes/OpenShell gate ran. Remote delivery retains
the documented [public SDK capability dependency](../../integrations/run-engine-private-receiver-delivery-request.md).
No companion-project code was changed. This closes the trusted Local artifact
capability checkpoint, not the complete credential milestone or platform goal.
