# Authored child call-site correlation — 2026-11-12

Initial Step C implementation; C8 authoring/observation and C9 remote acceptance
remain open.

`ExecutionRecord.call_site` identifies a dependency in the immediate parent
Program body: a graph `ProgramCallStep.uid` or custom coordinator dependency alias.
The shared compiler stamps it into each prepared child payload, for pinned and
owned targets. Native observation projects it into persisted execution records.
Runtime context/input rebinding preserves it. It participates in `request_digest`;
a different authored site cannot silently adopt the same child identity. Root
records reject a parent call site. Missing correlation stays unknown; current
compilation supplies it for children. The TypeScript contract exposes the field.

Repeated calls share an authored site and have distinct actual execution IDs.
`body_path` independently identifies the called owned body within its publication.
No correlation is inferred from engine-ID text. Per-Operation occurrences, retry/
attempt history, resumable projections, nested authoring and overlays remain open.

Program entrypoint contract is now `lumora-program-v11`; request format remains
v10. Matched API/worker/receiver code is required. The preceding C6 evidence is
scoped to its frozen v10 snapshot; remote v11 images have not been rebuilt.

## Verification

- 118 focused domain/execution-application/Run Engine adapter/native composition/
  architecture cases passed in 7.73s.
- A strengthened custom-to-custom assertion passed separately: 1 passed,
  12 deselected in 0.32s, overlapping the above suite.
- Native cases cover graph-to-graph, graph-to-custom-to-graph, custom-to-custom
  and distinct Repeat iterations sharing the authored body site.
- TypeScript `tsc --noEmit --incremental false`, changed execution Python import/
  undefined-name/syntax lint, and diff whitespace passed.

Source/test delta SHA-256: `86e84fb574702c3e3aed4d7b66e178b726e3d7d857a7217fa84a186cb348cbb7` (binary tracked diff plus sorted
untracked path/NUL/content under platform source/tests and UI source/tests).
Log: `/tmp/lumora-call-sites.log`. No paid calls, browser, Temporal rerun or remote
rebuild was performed for this observation slice.
