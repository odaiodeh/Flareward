# Unified Program model checkpoint

Recorded 2026-11-07 against the uncommitted worktree atop `cb44452d`. This completes
the requested model consolidation before resuming the broader, still-paused goal.
Existing designer/coding changes in the worktree were preserved and included in
verification. This is native/backend/UI-contract acceptance, not remote or browser
acceptance for the changed source.

## Model and implementation

The public model is Element -> Resource -> Program -> Execution. Operation is an
executable Element; a graph and registered backend coordinator are implementations
of one Program, using the same publication, admission, invocation and observation.
Construction references remain separate from execution edges. Specifications,
resources, factories, dependency bundles and builders remain the construction path.

`ProgramState` now has only portable input/results/values/output; output can be
structured JSON. State-based node/condition capabilities select `AgentProgramState`
and its engine adapter. Graph validation, channel admission, compilation and runtime
initialization select the same state contract. Node receivers expose the MAS view
and enforce actual writes; ordinary operations remain typed and graph-independent.
A cold-import guard verifies generic state does not initialize MAS graph state.

Sessions default to structured data with arbitrary bindings. Conversation is an
explicit interaction projection; ordinary Sessions allocate no conversation state.
Session and scheduled admission use the same projection, including cancellation.
A native two-turn backend Program scenario retains custom data without chat channels;
schedule tests cover both interaction modes. Conversation API views explicitly
require a conversation Session. Binding diagnostics omit supplied values.

The UI uses one Programs library and canvas/configuration editor. New Programs open
visual composition; installed implementations use their schema configuration.
Existing blueprint templates import into ordinary Program drafts, then use the same
save/publish/run lifecycle. The old workflow route, authoring page, creation canvas,
private hooks/loader and exclusively owned components are removed; current links
point to Programs. Shared read-only MAS flow views remain for chat/template/schedule
integrations. The complete occurrence/attempt execution workspace remains open.

Root/platform/UI READMEs, target design, development guide, status/plan and affected
repository skills use the canonical terminology. Receiver contracts are Program v6,
state v4 and elements v4; prepared request remains v10. Rebuild remote receivers at
the next installed-image milestone. No companion Run Engine changes were made.

## Verification

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/run_engine \
  multi-agent/tests/integration/run_engine multi-agent/tests/integration/http \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**1,047 passed, 30 skipped in 38.34s**. This includes native thread/process graph,
backend, nesting, operation, state, Session, template import and HTTP contracts.
Skipped cases require explicitly selected services/client options. The final gate
allowed temporary localhost listeners; an earlier sandboxed run blocked the artifact
restart and two CLI-process cases at socket bind. All three pass in the final gate.
A nullable-conversation change exposed scheduled admission's direct graph-state
assumption; it now uses the shared projection and the full gate passes.

`npm run typecheck`, `npm run test:contracts` and `npm run build` pass in `ui`.
UI contracts cover fresh graph definitions and template import URL/body/owner/signal.
Build retains vendor circular-chunk, mixed import and chunk-size warnings.
Strict mypy passes eleven affected application/state/session/scheduling modules and
five engine/HTTP adapter modules (`--strict --follow-imports=silent`; adapter run uses
`MYPYPATH=multi-agent/lib:multi-agent/adapters:multi-agent/plugins:multi-agent`). Ruff
check/format and `git diff --check` pass for the changed Python scope. The three
updated repository skills pass the skill-creator validator.

No Docker, Kubernetes/OpenShell, Temporal recovery matrix, paid model call or new
browser acceptance was run. Earlier remote/image evidence retains its original
source scope. These remaining gates and service retirement remain in the full goal.

## Source identity

Sorted manifests hash `path + NUL + SHA256(bytes)` per file, joined by newlines.
Production Python uses lib/adapters/bootstrap/config/plugins under multi-agent;
UI uses .ts/.tsx files under ui/client/src and ui/shared. Test/doc changes are
recorded by the worktree rather than included in these production aggregates.

| Source | Files | Manifest SHA-256 |
| --- | ---: | --- |
| Platform Python | 1,078 | `62a395a5a026bcb310170ebf648cc5d9807fea7fa47eb30384157cb6f1db91e2` |
| UI TypeScript | 365 | `e65a7a9d5db371bbd2f965955b9921bede1d0b8b10049266751cfda8f7a3c83b` |
