# Git candidates and alternative completion

Use `plugins.adlc.programs.git_coding` for `coding_git_candidate@1` and
`plugins.git.elements.specification` for normal Git provider/resolve/read operations.
The agent owns its Git commands and publication through already authorized tools.
Its final answer must be only a `GitRevision` JSON object (`repository`, full
immutable `commit`). The Program resolves that exact commit through its captured
admitted repository resource before returning an Engineering candidate. A valid
JSON claim alone is insufficient; unavailable or foreign revisions must fail.

Configure coding, artifact loading and repository placement separately. Repository
locations/owners remain receiver/operator bindings in `LUMORA_GIT_REPOSITORIES`.
The coding receiver needs its own authorized publication tools; a repository ID or
read binding grants no write authority. Never fix missing publishing access by
exposing operator keys or all-root configuration to the agent. Repairs receive the
prior exact revision and bounded reports; the agent handles branch/worktree commands.

`read_git_file` reads bounded regular-file bytes from an exact admitted commit,
using temporary Git storage. It refuses links, missing files and excessive data;
it does not run filters/submodules or install a checkout. Keep normal owner/type
checks, contained paths, safe process diagnostics and owned cleanup. Git uses the
shared proxy/TLS environment filter, excluding unrelated application/provider material.
Git CLI must be installed at repository placement; test receivers arrange this and
the production image offers `INSTALL_GIT=true`. New image paths still require a
matched build/verification gate before claiming remote support.

For independent Python checks, install `plugins.testing.programs.git_check` and pin
`git_python_function_check@1` under a separately authorized verifier owner. The
coordinator reads exact Git bytes on trusted source placement and reuses the normal
Python evaluator/comparator. Evaluator version 2.0.0 accepts `source: InlineContent`
and arguments; it receives no artifact ID, Git binding, expected answer or check
authority. Blob verifier transport still uses `CheckProgramInput.artifact` before
the trusted coordinator extracts bytes. Do not fabricate a managed artifact ID for
unpublished Git content or restore the old evaluator field as an alias.

Run focused application cases and actual Git adapter cases first. At the coherent
native milestone:

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  platform/tests/integration/coding/test_completion_choices.py -q
```

This uses real Git/HTTP/Mongo/Redis and thread/process invocation, with a controlled
Codex protocol executable. It publishes one Engineering revision, selects file directly
and Git through a pinned Feature child after design approval, fails/repairs each
candidate, inspects exact evidence and retrieves
source/reports after removing temporary compute. It makes no paid calls and proves
neither live Git credentials, remote isolation nor permanent repository retention.

`support.engineering_api` now accepts `verification_policies` and `check_programs`
maps. Test actors/bindings are indexed by runner ID in `api.verifiers` and
`api.check_bindings`. Reuse this transport owner and `CheckProgramSetup`; do not add
another verifier service or scheduler. The controlled CLI's retained-repository
binding is private test setup, never a portable Program field. Give distinct saved
coding resources distinct names. See the
[checkpoint](../../../../docs/evidence/2026-11-08-git-completion.md) for actual scope.
