---
name: debug-execution-policies
description: Diagnose owner-scoped execution-profile access and Lumora OpenShell startup policies, egress enforcement and retained-environment policy ownership.
---

# Diagnose execution policies

For owner/profile permission failures, start with
[owner-scoped profiles](../../../docs/program-platform-development.md#owner-scoped-execution-profiles).
`LUMORA_PROFILE_ACCESS` is separate from OpenShell network/process policy files.
No access policy means the installed deployment catalog; a configured policy
denies unmatched owners unless an explicit default grant exists. Match user/team
type and stable id, not display name. Duplicate owners or unknown profile names
fail startup; explicit owner denial overrides the default.

Trace the same application `ProfileAccess` resolution through catalog, preview
and compiler. Prepared backend Program targets must contain only the owner grant,
including nested owned/pinned scopes. Named environments cannot bypass profile
checks; borrowing still needs published imports. Runtime selection outside the
frozen set raises `PlacementRefused` before dispatch. Safe `admitted_profiles`
metadata is immutable request identity, not actual per-occurrence placement.
Scheduled template-to-tick admission must preserve profiles and work limits.

UI profile queries must pass team scope and isolate caches by actor plus owner.
Do not broaden server grants to fix a personal/team discovery mismatch. Current
policy changes apply to new preparation, not immediate revocation of running work.
Use application `test_profile_access.py`, Mongo `test_profile_access.py`, snapshot/
schedule tests and the production Programs client journey. Focused checks do not
establish Temporal/remote recovery, identity-provider membership or load behavior.

Read [the profile policy contract](../../../docs/program-platform-development.md#openshell-policy-configuration)
and the selected deployment's existing profiles. This workflow is for Run Engine
OpenShell placement. The retired sandbox element/tool proxy is not a control point.

`PlatformSettings.execution_policy_files` maps installed OpenShell profile names to
absolute JSON paths. `lumora.bootstrap.settings.execution_policies.load_execution_profiles` loads them
off-loop at API startup, before client allocation. Inline/file conflicts fail.
The compiler detaches the data; editing a file does not mutate existing requests
or named environments. Restart the API to load changes for new submissions.
Programs select approved profile names, not policy paths or SDK configuration.

Check the installed SDK source identity against the committed baseline in
[integration status](../../../integrations/README.md) when filesystem, process or
Landlock fields fail validation. Do not apply archived patches to the committed SDK.
The SDK receives a complete replacement policy, not a network overlay. Retain the selected image's required baseline. The shipped JSON example
is opt-in and tailored to the test image, including its Python paths and explicit
Landlock compatibility. A pre-existing sandbox retains its external owner's policy;
pairing `sandbox_id` with policy/file is rejected rather than silently ignored.

The current portable network subset is hosts/ports and executable paths. A full
URL, embedded port, path/method filter or unknown field is not supported by this
adapter. Keep SDK translation in Run Engine; keep file loading in composition.
Do not add SDK models to Lumora domain or application ports.

For actual enforcement, prepare [Lumora's independent test infrastructure](../../../platform/tests/infra/README.md)
and refresh the sandbox image after installed-source changes. Use:

```sh
.venv/bin/python -m pytest platform/tests/integration/deployment/test_openshell_policies.py --platform-backends=openshell --platform-hosts=local,temporal -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

The module reuses the production profile loader and shared API/worker/backend
fixtures. `support/network_probe.py` is the installed application element;
`support/http_probe.py` owns test HTTP connections. Keep those responsibilities
separate. Both local destinations must work in the positive control. In the
restricted case, one still works and the other must receive zero requests.
An arbitrary connection failure alone is not evidence of policy enforcement.

Cover both invocation-owned and retained environments: they use distinct engine
creation paths. Verify physical cleanup and native history replay. API/gateway
health or accepted policy input alone does not establish receiver connectivity or
enforcement. Record the image identity, gateway version, host/lifetime matrix and
unsupported policy fields; do not generalize the result to other kernels or the
full OpenShell schema. No paid provider calls are needed for these tests.

The focused `integration/deployment/test_candidate_policies.py` cases use normal
OpenShell by default. They compare real candidate subprocess outcomes outside the
sandbox: positive reachability, selective denial, offline execution, non-root
identity, host-file separation and private environment exclusion. Preserve injected
proxy/TLS transport settings when launching a filtered child environment; direct
network attempts may be unreachable even when the endpoint is allowed.

Only explicit `--strict-sandbox-filesystem` adds Landlock filesystem enforcement
and write-denial checks. A host without `CONFIG_SECURITY_LANDLOCK` cannot satisfy
that stronger profile; it does not block normal OpenShell workflow acceptance.
An opaque closed exec relay can hide supervisor restart after a brief ready state.
Inspect the exact owned container's state/stderr. Invocation cleanup can remove those
logs, so a bounded credential-free diagnostic sandbox may be needed; remove its
sandbox and workspace and verify absence after asynchronous deletion. Never infer
cleanup from one acknowledgement or claim optional filesystem enforcement from a
normal-profile pass.
The [current diagnosis](../../../docs/evidence/2026-11-05-candidate-profile.md)
records the unsupported Docker Desktop kernel, fresh mTLS state and tested images.
