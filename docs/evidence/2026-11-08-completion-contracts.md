# Declared Engineering completion choices

Engineering now publishes named completion choices instead of one implicit
candidate/verification configuration. This is the first backend checkpoint of the
completion-and-delivery milestone, not acceptance of real Git/Jira/CI delivery.

## Implemented behavior

`engineering@3` configuration contains `completions` and `default_completion`.
Each `EngineeringCompletion` records:

- A unique name and bundled candidate-result JSON Schema.
- Implementation/repair child aliases and a finite repair bound.
- Verification policy ID, exact required checks, permitted verifier IDs and whether
  each check requires reports, plus the runner IDs to invoke.
- Human Review configuration using normal scoped operation bundles.

Invocation supplies `task` and optionally a declared `completion` name. The default
is frozen in the publication. Undeclared choices fail before producer dispatch.
The worker result must match both `EngineeringCandidate` and the selected schema
before any verification/review effect. Actual plans must preserve the configured
requirements as well as policy and candidate; a changed operator policy cannot
silently omit checks, choose another verifier or drop required reports.

The selected name is retained in `EngineeringResult` and the ADLC-owned
`engineering-review@2` subject alongside the exact candidate and accepted evidence.
Result validation rejects a substituted name or snapshot. Design and Engineering
now compare the existing review-specification fingerprints rather than Python dict
equality, which conflates some numeric/boolean values. Scalar-type substitutions
cannot silently identify the same reviewed payload.

This uses the same coordinator, child runtime port, service operations and ordinary
Program lifecycle. No Git branch, candidate registry, scheduler, environment manager
or generic mandatory result envelope was added. Ordinary operation outputs remain
their own typed data. Engineering's subject envelope is an opt-in ADLC contract.
Human Review remains its independent reusable Program; the ADLC review subject does
not change generic reviewer authorization, persistence or engine waiting.

## Publication and boundaries

`ChildContract.result_schema` adds configured projected-result constraints beside
existing Pydantic result models. The application-owned interface checker rejects
provably disjoint types, finite values and required object members. It preserves
JSON Schema numeric equality (`1` and `1.0`) and distinguishes booleans from numbers.
This schema-overlap behavior is distinct from exact signed/reviewed JSON identity.
Optional disjoint members may be omitted. Open/complex/recursive schemas retain
runtime checks; this is not complete JSON Schema subtyping.

Candidate schemas use the existing bundled Draft 2020-12 validation with no network
resolution. Invalid/remote references return constant diagnostics without input
contents. Shared child aliases require identical candidate schemas; different aliases
may reference the same published Program. Both default and nondefault choices must
declare valid child dependencies at publication.

Relevant production source:

- `multi-agent/plugins/mas_plugins/engineering/program.py`: configuration, selection,
  candidate validation, requirement fences and the existing coordinator.
- `multi-agent/plugins/mas_plugins/engineering/review.py`: exact ADLC review subject.
- `multi-agent/plugins/mas_plugins/engineering/design.py`: canonical reviewed identity.
- `multi-agent/lib/mas/application/programs/{ports,contracts,interfaces}.py`:
  generic declared result constraints and conservative compatibility checks.

## Verification

```sh
.venv/bin/python -m pytest multi-agent/tests/domain multi-agent/tests/application multi-agent/tests/architecture -q --color=no
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/verification/test_engineering_workflow.py multi-agent/tests/integration/verification/test_coding_feature.py multi-agent/tests/integration/coding/test_feature_workflow.py -q --color=no
```

**837 shared/domain/application/boundary cases pass in 7.46s. Eight native cases pass
in 77.97s.** The final gates used frozen source. Focused lint/format checks pass;
six affected production modules pass strict mypy with silent imported dependencies
and ignored missing third-party stubs. This does not establish whole-repository typing.

New application cases exercise one unchanged configuration with file/Git-shaped
contracts, default and explicit selection, refused unknown names, malformed identities,
mutable branch names, invalid schemas, conflicting aliases and incompatible producer
publication. These use owned runtime-port doubles with real application review/check
services; they do not produce or independently inspect an actual Git commit.

The native cases use real HTTP, signed cookies, Mongo, Redis and Local thread/process
execution. They preserve standalone/nested Engineering reuse, rejected/revised design,
failed-check repair, exact final review, capability cleanup and retained file output.
Coding uses the production CLI adapter with a controlled executable. No paid calls,
new browser journey, Docker rebuild or OpenShell/Kubernetes/Temporal gate ran here.
The first native run passed before the requirement fence; the final run above includes it.

[The source manifest](2026-11-08-completion-contracts-source.json) identifies the
production and fixture/test snapshot. Development callers now publish Engineering 3;
versions 1/2 are not registered aliases. Old development publications must be recreated.

## Remaining milestone work

The earlier [live authored checkpoint](2026-11-08-live-feature-authoring.md) proves its
version-2 images. Changed installed code requires new matched images at the next
remote milestone; historical live acceptance is not current-source proof.

Next, prove real immutable Git availability/retention and managed-file alternatives
through one published Engineering definition, then integrate delivery capabilities
and larger Jira-to-CI/CD composition. Current selection is available directly on
Engineering; the Feature wrapper still uses its child's configured default.
Authoring/invocation UX for choices, policy discovery, actual browser acceptance,
external-effect recovery and broader remote matrices remain unfinished. This
checkpoint does not certify arbitrary work completion or massive-scale operation.
