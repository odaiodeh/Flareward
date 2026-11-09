# File and Git completion through one Engineering publication

One published Engineering revision now runs with either a managed-file or an
immutable Git completion choice. Both paths perform trusted checks, restore failed
work/report context for repair, request final review of exact accepted evidence,
and preserve output after temporary coding workspaces are removed.

## Implemented capability and ownership

- `mas_plugins.engineering.git_coding` registers `coding_git_candidate@1` with typed
  configuration/input/output metadata. Normal saved resources, factories/builders,
  publication, child calls and invocation ports remain in use.
- The configured coding agent owns Git commands and publication using its already
  authorized tools. The Program validates its JSON `GitRevision`, rejects mutable
  or foreign references and independently resolves the reported commit through an
  admitted repository resource before returning `git-revision@1`.
- Git read access does not grant publication authority. No Git write credentials,
  URL selection, sandbox management or Git-specific compiler branch was added.
  Repository administration owns ongoing retention. The native fixture's agent
  publishes to retained refs in its owned bare repository; this is not a permanent
  archival lease or proof of live remote publishing credentials.
- A new normal `read_git_file` operation uses an application-owned `GitFileReader`
  port. The Git adapter fetches the exact commit into owned temporary storage and
  returns bounded regular-file bytes with revision/path/hash/size. Links, missing
  files and excessive content fail closed; filters/submodules are not executed.
- `git_python_function_check@1` reads exact admitted source on trusted repository
  placement, checks the returned identity/path and reuses the existing evaluator
  and trusted comparison. Expected answers and repository bindings stay outside
  evaluation placement. Reports identify the original Git candidate fingerprint.
- Evaluator implementation **2.0.0** accepts `source: InlineContent` and arguments.
  It needs no artifact ID, repository connection or verification authority. The
  trusted blob verifier still receives `CheckProgramInput.artifact`, validates its
  exact identity and extracts bytes. No fake blob reference represents Git content.
  Old evaluator fields/version-1 bundles are not supported compatibility paths.

Coding, artifact loading and repository inspection retain separate placement
selections. The source/evaluation boundary uses the same portable byte contract
for file/Git work. The generic Program runtime and Run Engine were not changed.
`coding_feature@1` now forwards optional `completion` separately from the coding
task and rejects a child result identifying a different requested choice. Omission
preserves the pinned Engineering revision's default. Engineering owns declared-choice
validation; the wrapper does not duplicate or inspect its child's configuration.

## Native end-to-end proof

The scenario in `integration/coding/test_completion_choices.py` runs under both
Local thread and process invocation:

1. Create an owned retained bare Git repository and private test-side publishing
   binding. Register normal Git operations and two independently pinned verifier
   Programs under a separate verifier owner.
2. Create protected saved file/Git coding resources. Publish their candidate Programs
   and **one** Engineering revision with declared file/Git schemas, child pins and
   frozen check/verifier/report requirements.
3. Invoke that unchanged revision directly with its default file completion. Then
   invoke a Feature Program selecting Git and pinning the same Engineering revision.
   Approve its exact design; Engineering/checks cannot start before this approval.
   Neither invocation edits or republishes the Engineering definition.
4. Each first candidate fails three actual Python function cases. File repair
   restores source/report bytes; Git repair fetches the exact previous commit and
   reads the failed report before producing/publishing a successor commit.
5. Each repaired candidate passes. Pending final review identifies the selected
   choice, exact candidate and accepted report; the authorized synthetic reviewer
   approves that occurrence. Both roots return `verified` with two attempts.
6. Candidate ownership receives 403 on private verifier executions; the verifier
   actor sees the pinned private Program. Independent check results, rather than
   the coding agent's success claim, supply evidence.
7. Delete the temporary coding workspaces. Fresh API downloads retrieve the file
   and reports; a newly executed graph Program reads the exact retained Git file
   through the normal operation. All content hashes match. Six managed capabilities
   retire per profile, leaving no credential fields/files or pending cleanup.

HTTP, signed sessions, Mongo, Redis, Git commands, process workers, source retention,
Python evaluation and report collection are real. Codex protocol behavior and
external identity/settings are controlled. There are no paid provider calls or
actual human browser decisions in this gate. Local controlled-code evaluation is
explicitly enabled; it does not establish hostile-code isolation.

## Verification

```sh
.venv/bin/python -m pytest multi-agent/tests/application/test_coding_git_candidate.py multi-agent/tests/application/test_git_python_check.py multi-agent/tests/application/test_python_function_program.py multi-agent/tests/integration/repositories/test_git.py multi-agent/tests/integration/catalog/test_git_plugin.py -q --color=no
.venv/bin/python -m pytest multi-agent/tests/domain multi-agent/tests/application multi-agent/tests/architecture multi-agent/tests/adapters/test_live_browser_lifetime.py -q --color=no
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/coding/test_completion_choices.py -q --color=no
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/coding/test_feature_workflow.py multi-agent/tests/integration/verification/test_program_checks.py -k 'approved_feature or operator_pinned' -q --color=no
```

- 46 focused application/real-Git/catalog cases pass in 13.95s, including approved
  proxy/TLS preservation and exclusion of application/provider environment material.
- 858 domain/application/boundary/cleanup-guard cases pass in 8.40s, including default,
  explicit and alternative Feature selections and rejection of substituted choice results.
- Both native completion/composition cases pass on the final runtime source in 43.61s.
  The earlier direct-only gate passed in 38.40s before Feature propagation.
- Ten existing native feature/verifier cases pass in 91.54s, four deselected,
  including repair and fresh report retrieval after completed-state API restart.
- Twelve selected production modules pass strict mypy with silent imported dependencies
  and ignored missing third-party stubs. All 43 changed Python files pass lint/format.

The existing-feature regression gate preceded Git transport/Feature changes; its
exercised file runtime stayed unchanged. The focused Git, final shared and native
completion/composition gates include the relevant final changes. Exact source and result identities
are in [the manifest](2026-11-08-git-completion-source.json).
After the native gate, only one test assertion's whitespace was reformatted.

An initial native attempt failed during setup because the two saved coders used the
same name; no feature execution had started. Distinct names corrected the fixture.
Its normal context teardown completed before the rerun. Successful fixtures close
owned API/identity sessions and uniquely scoped databases; shared services remain.

## Packaging and remaining acceptance

The existing cached OpenShell base was inspected and supplies `/usr/bin/git`
(Ubuntu 24.04). The test receiver Dockerfile now installs Git if absent; production
images can opt in using `INSTALL_GIT=true`. Those Dockerfile paths have **not** been
built/accepted here. Rebuild matched receivers and recapture evaluator-2 bundles at
the next remote milestone. Prior live/OpenShell evidence retains its older snapshot.

Still required: live agent Git publishing, write-credential provisioning, appropriate
remote isolation/recovery, choice authoring/invocation and Git-source review UI,
larger unchanged Jira-to-CI/CD composition and
delivery/validation with uncertain-effect reconciliation. The check demonstrates
one small function/file per commit, not a complete repository audit, all task
satisfaction criteria, scalability or permanent source retention guarantees.
