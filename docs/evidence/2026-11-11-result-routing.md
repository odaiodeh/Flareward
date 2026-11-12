# Typed graph result routing — 2026-11-11

This record completes the documentation interrupted after the routing gate. Its
results describe the November 11 worktree, before the November 12 coordinator
strategy/naming refinement. Current-source verification is separately scoped.

## Implemented contract

`GraphDefinition.conditions` is a discriminated `ConditionalRoute | ResultRoute`
union. Serialized routes require `kind: condition` or `kind: result`.
`ResultRoute.selection` uses ordinary path/literal bindings in the post-source
scope, including the source's recorded result. Saved condition Elements remain
supported through their explicit MAS state adapter.

The compiler lowers result routing to Run Engine native conditional edges with
strict unknown-label handling. The application-owned normalizer accepts booleans,
string labels and lists/tuples of strings, and validates the entire selection
before scheduling successors. An empty list selects no successors. Invalid types
or unknown labels fail without echoing selected values in diagnostics.

No Element construction or MAS conversion is required for result-only graphs.
Operation and Program outputs can drive routes. Existing joins, placement and
native retry semantics remain engine-owned. The UI route editor supports result
bindings and saved conditions through the existing graph authoring surface.

## Recorded verification

- 958 domain/application/architecture/native-routing cases passed in 16.50s.
- Final native routing gate: 21 passed in 4.01s; two additional thread/process
  mixed result/condition cases passed separately. These counts overlap.
- Production Programs TypeScript client against the native FastAPI/Mongo/Redis
  fixture: 1 passed, 10 deselected, in 11.12s. Covers publication, result branches,
  and refusal of invalid complete selections before successor execution.
- UI typecheck, contract checks and production build passed. The build retained
  the existing large-chunk warnings. Changed Python static checks passed.

The recorded source/test delta SHA-256 was
`c1ed18f54a8bf63cb8598af19aae6f948096463a82812a8501c02bd644b25277`;
this is a worktree evidence identity, not a Git commit. Program entrypoint contract
became `lumora-program-v10`; request remained v10. Run Engine was unchanged at
`60393440efd3876cd6c81e0b013e8bf6d9167659`.

Local logs: `/tmp/lumora-result-routing-regression.log`,
`/tmp/lumora-result-routing-final-native.log`,
`/tmp/lumora-result-routing-mixed.log`,
`/tmp/lumora-result-routing-client.log`, and the corresponding UI/build logs.
These temporary logs may expire; this record states their scope explicitly.

No Temporal replay, browser acceptance, paid model calls or matched remote image
matrix was performed by this gate. Those milestone obligations remain open.
