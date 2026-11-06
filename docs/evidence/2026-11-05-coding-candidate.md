# Coding operation to durable Engineering candidate

Recorded 2026-11-05. The revised goal prioritizes an integrated feature journey
rather than completing every control or administrative migration first. This is
one production integration step toward that journey, not product acceptance.

## Implemented capability

The optional `mas_plugins.engineering.coding` module registers
`coding_file_candidate@1` using the existing Program registration/configuration/
invocation path. Its coordinator invokes configured coding and publication operation
bundles. It publishes a configured relative file from the actual returned coding
workspace, then returns the published blob identity as an `EngineeringCandidate`.
Agent prose is never interpreted as verification or as the content identity.

Engineering work supports a typed task parameter. The installed `CodingFileWork`
subclass exposes `CodingInput` prompt/context fields in its schema and has a stable
importable identity for native invocation. Generic Engineering tasks and alternative
candidate representations remain supported. This is a single-file extension, not a
Git requirement or a restriction on repository/multi-file Programs.

Typed effect results, contained paths, configured placement and cancellation are
preserved. Failed/cancelled coding cannot proceed to publication. Prior feedback is
provided as context, but previous candidate bytes are not yet restored for repair.
Trusted verification, exact-candidate review and bounded iteration remain owned by
the surrounding Engineering Program and application services.

## Source identity

The `coding_candidate` group in
[the focused source manifest](2026-11-05-product-checkpoint-source.json) records four
files, aggregate SHA-256
`585335a499ee7b10b866aaf11205e41fc2d6855f2cd022492aeba35e6549bbec`.
Python is 3.14.6. This is a focused checkout identity, not a complete dependency or
receiver-image manifest. No Run Engine code was changed.

## Verification and encountered failure

Final shared gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/mongo/test_resource_inspection.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**692 passed in 6.08s**, no skips or reported warnings. This includes the new
candidate contracts, generic Engineering regression, domain/boundary coverage and
inspection probe cases. It is not 692 new tests or complete platform acceptance.
A focused final candidate/Engineering/architecture selection passed **37 in 3.51s**.

The first typed generic specialization passed application tests but failed native
invocation: its generated `EngineeringWork[CodingInput]` name could not resolve as
an installed distributed function. A mixed native gate ended **2 failed, 4 passed
in 38.20s**: both candidate variants failed; both graph handoffs and the two existing
Engineering fixture-byte/managed-grant journeys passed. The fix is the named
`CodingFileWork` subclass; the typed schema was retained.

Final affected native gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/coding/test_artifact_handoff.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**4 passed in 22.35s**, no skips or reported warnings. Both graph and backend Program
producers use the real CLI adapter/protocol subprocess and production artifact API
on Local thread/process receivers. After destroying the compute workspace and
restarting the artifact API, the consumer restores exact bytes using the production
materializer. The final gate fixes both previously failing variants.

Strict mypy passes for both Engineering production modules; all 18 Python files
across the checkpoint groups pass Ruff lint/format. UI typecheck passes. The coding
diagnostic skill documents the portable-model failure/fix and passes its validator.

## Scope and remaining work

The subprocess is a deterministic Codex protocol executable, not a live model.
Artifact and coding credentials are explicitly supplied private operator files in
this gate; it does not prove automatic root-scoped provisioning for this composition.
The existing Engineering cases separately prove managed artifact/review/check grants
with fixture candidates. Combining these paths remains required.

No actual browser, feature-design approval, trusted coding checks/repair, paid agent,
real Jira/CI/CD, Temporal restart/replay, remote image or load acceptance is claimed.
Both coding and publisher must access the same physical workspace; isolated execution
requires explicit environment binding, not repeated profile selection alone.

Next: compose versioned feature design and authorized approval, integrate coding
candidates with meaningful checks/repair feedback and managed authority, connect the
thin UI, then run bounded live-agent acceptance and unchanged nested reuse. Remaining
hardening/migration obligations remain in the full goal and target checklist.
