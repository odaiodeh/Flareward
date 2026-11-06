# Controlled Engineering browser journey

Use this when checking the actual App, managed workflow consent and durable output
inspection together. It uses the production verifier integration with controlled
source. It is not live-model, OAuth, cross-owner attachment, remote isolation or
complete authoring acceptance.

Build assets from `ui/` before starting the runner:

```sh
NODE_ENV=production node tests/build-placement-browser.mjs /tmp/unifai-feature-browser-assets
```

Start from the repository root with dedicated services and a fresh owned directory:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
PYTHONPATH=multi-agent/tests:multi-agent/lib:multi-agent/adapters:multi-agent:multi-agent/plugins \
.venv/bin/python -m support.feature_browser \
  --assets /tmp/unifai-feature-browser-assets \
  --directory /tmp/unifai-feature-browser-run
```

Keep the live handle and open its printed login URL. The fixture publishes saved
encrypted coding resources and normal Design/Engineering/Feature revisions through
the real API. The synthetic owner is also the assigned reviewer, permitting normal
owner-authorized artifact inspection. Do not widen cross-owner access to make it work.
No workflow grants are pre-issued. Design and the coding executable are controlled
peers. The normal API dispatches `program@1` to a separately owned, digest-pinned
`python_function_check@1` Program. Its evaluator receives source and arguments;
the coordinator retains expected answers. Local evaluation is explicitly enabled
for controlled fixture code and is not a hostile-code sandbox.

Open Feature revision 1. Enter a small addition task and acceptance criterion.
Explicitly select these workflow permissions through the shared schema fields:

| Capability | Scope | Lease |
| --- | --- | --- |
| Human review requests | policy `release@1`; actions `open`, `read`, `close` | 3600 seconds |
| Verification plans and checks | policy `engineering@1`; actions `create`, `read`, `run_check` | 3600 seconds |
| Artifact content | namespaces `engineering`, `verification-reports`; actions `read`, `publish`; max bytes 65536 | 3600 seconds |

The catalog describes owner-filtered scopes; it grants nothing. Verify approval is
required and editing scopes resets it. Approve and start. The shared execution URL
must show the actual root and observed children. Verify no `workspaces/**/started`
marker exists before design approval. Inspect the exact versioned design and approve.

The first controlled coding attempt fails the independent check. Repair restores
source and reports into a fresh workspace; expect two coding `started` markers.
Reports use `details.failures`, not the removed test peer's top-level `failures`.
The final review identifies an exact blob reference. Inspect it and preview verified
text before approving. Completion must report `verified`, two attempts, accepted
verification with report references and persisted final human approval.

After confirmed completion, remove only this fixture's `workspaces` directory while
keeping its API and `artifacts` storage alive. Reload the execution, reopen source
and report cards, and preview both again. A retained browser preview is insufficient
proof of durable retrieval. Save a screenshot of the reloaded content.

Check retirement in the unique owned Mongo database: three material reservations,
no unretired/cleanup-pending rows and no remaining `credential` fields. Do not print
stored material. No credential `*.json` files should remain. The file-delivery
adapter deliberately retains one-byte `.json.lock` markers containing `R`; they
fence delayed writers and are not credential leaks. Do not delete active lock inodes.

Manual review deadlines are 600 seconds; automated scenario defaults remain 60.
An expired review is closed/unsatisfied, never retroactively approved. Use a new
invocation after a terminal expiry. Observation timeout alone does not permit
restarting the fixture or replacing live work.

Close the tab, send Ctrl-C once to the owned runner and poll that same handle.
Confirm API/identity shutdown, private cookie deletion and printed removal of its
unique database. Keep shared Mongo/Redis services running. Record controlled peers
and unverified behavior separately from actual product acceptance. The
[production-checker browser checkpoint](../../../../docs/evidence/2026-11-06-engineering-program-checks.md)
records the native gate, authority separation and retained output proof.
