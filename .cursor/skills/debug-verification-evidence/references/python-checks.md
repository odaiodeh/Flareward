# Python function checker and inline input

Use this for `operations/python_function_evaluate`, `python_function_check@1` and candidate input
failures. It is an optional testing plugin, not a new engine or universal Python
sandbox. Use the [implemented contracts](../../../../docs/program-platform-development.md#python-function-checks-and-bounded-candidate-transport)
and selected [checkpoint](../../../../docs/evidence/2026-11-05-python-checks.md).

The operator pins the verifier Program normally and sets
`input_artifact_max_bytes` on its private Program-check binding (maximum 1 MiB).
Only a canonical `blob-artifact@1` subject is valid. The runner reads bytes as the
policy-admitted candidate owner through ArtifactService, bounds the stream and
verifies length/hash into `InlineArtifact`. The verifier receives source data,
not an artifact token or all-root capability. Stored inputs/history include that
bounded source; larger repository transport must use a separate appropriate contract.
Metadata-only checks omit the artifact field. Preserve their pinned input schemas.

Install `plugins.testing.specification` for the normal evaluator spec/factory/
builder and `plugins.testing.programs.python_check` for the verifier backend Program. Its
configuration captures an evaluator bundle, expected cases and explicit placement.
The evaluator resource has only function/timeout configuration; its inputs contain
`source: InlineContent` and arguments, without artifact IDs, Git connections,
verification metadata, capabilities or expected answers. Evaluator spec version 2.0.0
replaces the old `artifact` invocation field; recapture old bundles and rebuild images.
The trusted
Program compares returned values. The old combined check operation was removed;
fresh configurations must capture the evaluator and publish a verifier Program.

For `git-revision@1`, use `plugins.testing.programs.git_check` and
`git_python_function_check@1`. It reads exact source with a captured `read_git_file`
operation on trusted repository placement, then reuses the byte evaluator. Preserve
the original Git fingerprint in its result/report and keep expected answers and
Git bindings outside the evaluator. Native file/Git choice proof is in
`integration/coding/test_completion_choices.py`; it uses controlled coding and real
Git/HTTP/storage, not a live provider or remote sandbox. See
[the checkpoint](../../../../docs/evidence/2026-11-08-git-completion.md).

Factory execution defaults to disabled. Receiver/operator settings may supply
`FLAREWARD_PYTHON_CHECK_EXECUTION_ENABLED=true` and an absolute
`FLAREWARD_PYTHON_CHECK_DIRECTORY`. Resource configuration cannot enable it. The flag
is an operator authorization assertion, not evidence of physical isolation. Do
not enable it for live/untrusted code on a trusted host merely to make a test pass.
`-I -S` disables import/user configuration, not OS/filesystem/network access.

Expected answers stay in the coordinator outside the candidate receiver, not merely
outside child stdin. Returned actual values/failure are untrusted and schema/count/
byte validated before comparison. JSON booleans/numbers remain distinct. stdout/
stderr and case/report data are bounded. Raw diagnostics must not become evidence.
The actual restricted profile, not this protocol alone, establishes OS isolation.
Preserve the receiver's injected proxy/TLS transport when filtering the child
environment. `plugins.processes.network_environment` is shared with Codex;
it excludes provider keys, workflow fields and invocation payloads. Native PATH-only
execution can pass while OpenShell's allowed network route is unreachable. The
[normal OpenShell checkpoint](../../../../docs/evidence/2026-11-06-normal-openshell.md)
proves positive/selective/offline behavior with this transport preserved.

For hangs or leaked processes, inspect acquire/TaskGroup/cancellation ownership:
finish assigning the subprocess before propagating cancellation, kill its process
group, reap it and remove the exact owned directory. Never kill an unrelated PID
or interpret an observation timeout as permission to restart live infrastructure.

Focused tests:

```sh
.venv/bin/python -m pytest platform/tests/adapters/test_python_function_checks.py \
  platform/tests/application/test_python_function_program.py \
  platform/tests/application/test_program_checks.py platform/tests/domain/test_artifacts.py -q
FLAREWARD_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
FLAREWARD_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest platform/tests/integration/verification/test_program_checks.py -q
```

Native fixture environment is a callback accepted by `support.server.api_process`,
not a dictionary. The maintained tests deliberately execute controlled source and
assert temp-directory cleanup. They also prove source/report owner boundaries and
report survival after completed-state API reconstruction. Native plan/root
cancellation now verifies terminal state, PID reaping and workspace collection.
Thread/process pools drain running invocations; finite operation deadlines are
necessary. Do not claim prompt preemption or increase observation timeouts without
inspecting actual state. See the [engine request](../../../../integrations/run-engine-invocation-cancellation-request.md).
For current-image remote checks, use `integration/deployment/test_program_checks.py`
with explicit `--platform-backends=k8s --platform-hosts=local`, dedicated service
URIs, kubeconfig/context and a freshly verified `FLAREWARD_TEST_K8S_IMAGE`. Its shared
`prepared_verifier(..., target=...)` disables local candidate evaluation and keeps
dispatcher settings separate from the receiver-local directory. Run Engine adds `RUNENGINE_PARAMS` to the declared
pod environment; compare names without printing that payload. The child environment
is independently minimized. Use the backend SDK observer for namespace/image/mount
proof, then `assert_clean()` for physical absence; a target setting alone is weaker.
The Kubernetes fixture disables service-account token mounting. Namespace display
uses a non-secret setting, not the removed token-volume dependency. See the focused
[placement evidence](../../../../docs/evidence/2026-11-05-checker-placement.md).
The later [boundary checkpoint](../../../../docs/evidence/2026-11-05-checker-boundary.md)
records the separated implementation and actual receiver parent-environment probe.

Same-UID candidate code can inspect receiver parent process data. The maintained
parent-environment probe tries to recover an answer from the actual invocation
payload; an unpredictable answer exists only in coordinator configuration. Require
a failed comparison with the explicit absent-answer actual value, not an execution
error that might hide an unexecuted probe. This is one concrete disclosure test,
not universal hostile-code certification. Verify actual profile restrictions before
live-source acceptance; native tests and protocol separation alone do not establish
network confinement, in-flight Temporal recovery, OpenShell acceptance or live coding.
