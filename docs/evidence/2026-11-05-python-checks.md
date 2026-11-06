# Python function checks and bounded verifier inputs

Recorded 2026-11-05. The optional checker now runs actual Python function cases
through the production Program-verification connection. All executed source here
is controlled fixture source. This is not live-agent or isolated-code acceptance.

## Changes and ownership

- `InlineArtifact` is an immutable, bounded content-transport value: exact blob
  reference plus base64 bytes validated by length and SHA-256, maximum 1 MiB.
  Raw data is omitted from its representation and input validation diagnostics.
- An operator Program-check binding may set `input_artifact_max_bytes`. Only a
  canonical blob subject is admitted. The application runner validates policy,
  reads through the existing ArtifactService as the admitted candidate owner,
  bounds the stream and supplies verified content in the normal verifier input.
  The verifier receives no new artifact credential or workflow capability. This
  deliberately stores bounded source in its private execution inputs/history.
- Metadata-only requests omit the optional content field. Their pinned input
  contracts remain usable. Source corruption, oversize input and noncanonical
  references cannot start a checker. Actual stored verifier input is revalidated
  before observing its result, without another storage read during reconciliation.
- `mas_plugins.testing.specification` registers `operations/python_function_check`
  through the normal spec/factory/builder/typed-operation path. Its configuration
  owns function name, argument/expected cases and deadline. The generic platform
  remains language-independent; no compiler or Run Engine branch was introduced.
- The adapter retains expected results in its parent comparator. A child Python
  process runs the source and returns actual values. Exact JSON comparison keeps
  booleans and numbers distinct. Failed cases produce failed evidence; exceptions,
  invalid/excessive output and deadlines produce explicit safe error reports.
- Process-group ownership, acquisition, concurrent bounded stdout/stderr reads,
  cancellation, reaping and temporary-directory cleanup remain adapter concerns.
  Physical sandbox placement/lifetime remains Run Engine's responsibility.
- Factory execution is disabled by default and can be enabled only by receiver
  settings. The operator flag does not establish OS isolation. A subprocess under
  the host user's identity is not a hostile-code sandbox. The native test enables
  it explicitly only for authored, controlled source.

## Verification

Final shared/static gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/test_verification_settings.py \
  multi-agent/tests/adapters/test_python_function_checks.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**759 passed in 7.48s**, no skips or reported warnings. Scope includes the two
adapter modules; it is not a shared-only count. Tests cover inline integrity and
representation, no receiver grant, owner-bound artifact reads, changed source,
unsupported transport configuration, canonical identities and existing boundaries.
Actual controlled subprocess cases cover addition/subtraction, ordinary debug
output, exceptions, output overflow, exact JSON answer types, minimal environment,
timeout/cancellation with acquired-process reaping and directory cleanup. Factory
enablement cannot come from authored configuration. These are behavior/ownership
checks, not assertions that mirror the implementation's wording.

Final native gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/verification/test_program_checks.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**8 passed in 61.55s**, no skips or reported warnings. Actual signed-cookie HTTP,
Mongo/Redis, production composition and thread/process workers exercise both
metadata and Python-check Programs with passing/failing candidates. Python source
is published by the candidate owner; the distinct verifier owner cannot directly
read that artifact. Only the admitted check receives bounded content through the
application service. Candidate owners cannot inspect the other owner's root.
Check results/reports refer to the exact candidate; workspaces are gone afterward.
Reconstructed APIs retrieve identical completed evidence and durable report bytes.

Strict mypy passes seven production files (artifact value, Program-check runner,
platform composition and the four-file testing plugin), using the existing
four-root MYPYPATH and `--strict --follow-imports=silent`. Focused Python source/tests
pass Ruff check/format and diff checks. The updated verification skill validates.
No UI code, Docker images or companion Run Engine code changed. Browser, broad
Temporal/Kubernetes/OpenShell and paid-provider gates were not run.

## Diagnostics and acceptance limits

The first native attempt failed all eight cases before checker API startup because
the fixture supplied a mapping where `api_process` requires an environment callback.
Corrected the caller; production execution policy was not changed. A subsequent
eight-case run passed. Review then refined metadata-only serialization to omit
unused inline content; the final eight-case gate above and shared gate followed.
Expected answers remain parent-side; raw child diagnostic strings are not evidence.

Inline transport is optional and bounded, not a replacement for large repository
or reference-based transfer. Same-UID hostile-process isolation, escaped descendants,
malicious-source resistance and correctness beyond configured cases are unproven.
Live source must use appropriate physical isolation and an admitted image/profile;
`-I -S`, a clean environment and an enable flag are insufficient evidence for that.

Next: couple verifier-job cleanup to parent-plan lifecycle, prove one current-image
isolated checker profile, and execute bounded live coding through Engineering.
Independent-root accounting, in-flight Temporal recovery, broader remote matrices,
complete authoring/browser acceptance and unchanged live Engineering reuse remain
required. A passing controlled Python check does not complete the product milestone.

## Source identity

[Focused manifest](2026-11-05-python-checks-source.json) identifies changed source,
shared fixtures and referenced execution/verification contracts. It is not a full
dependency or image manifest. Source aggregate SHA-256: `d8461a5b1029bbf091718d013fc567c5d8598f4244f2680a807996820fa69c0a`.
