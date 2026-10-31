---
name: debug-execution-policies
description: Configure and diagnose UnifAI OpenShell execution-profile policies, startup policy files, real egress allow/deny behavior, and retained-environment policy ownership.
---

# Diagnose execution policies

Read [the profile policy contract](../../../docs/program-platform-development.md#openshell-policy-configuration)
and the selected deployment's existing profiles. This workflow is for Run Engine
OpenShell placement. The retired sandbox element/tool proxy is not a control point.

`PlatformSettings.execution_policy_files` maps installed OpenShell profile names to
absolute JSON paths. `config.execution_policies.load_execution_profiles` loads them
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
Do not add SDK models to UnifAI domain or application ports.

For actual enforcement, prepare [UnifAI's independent test infrastructure](../../../multi-agent/tests/infra/README.md)
and refresh the sandbox image after installed-source changes. Use:

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_openshell_policies.py --platform-backends=openshell --platform-hosts=local,temporal -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
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
