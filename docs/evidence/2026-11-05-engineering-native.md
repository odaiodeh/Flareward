# Engineering: native Local execution slice

The same published Engineering revision ran independently and as a child of a
larger `Jira intake -> Engineering -> CI -> deployment validation` graph through
FastAPI, Local Run Engine, dedicated MongoDB/Redis and normal scoped operation
factories. Each run used a deterministic candidate child, a deterministic trusted
check adapter and an authenticated test reviewer. The first check failed; repair
produced a second synthetic document identity; the check and human review accepted
that exact identity. The graph's intake, CI and validation operations are test
peers, not real Jira, CI/CD or deployment integrations.

The test verifies the accepted evidence fingerprint, review decision, nested
published revision, one check per attempt, automatic scoped credential retirement
and absence of workflow bearer tokens from public results and the API log. The
candidate identity is a deterministic fixture; the test does not materialize or
independently verify the bytes of a real artifact.

Final-source Local thread and process cases passed independently (one each); the
focused application/verification/review/child-contract/architecture gate passed
52 tests. Strict mypy on the production Engineering module and Ruff for seven
Engineering source/test files passed. Earlier simpler thread/process runs also
passed but do not replace these final-source cases.

Temporal replay and restart, actual immutable artifact production, real external
integrations, browser/client Engineering journeys, Kubernetes/OpenShell execution,
and broader recovery and security acceptance remain unproven. This slice does not
complete the Engineering milestone or the overall platform goal.

The seven Engineering source/test files have aggregate SHA-256
`3a853c120ff66efd949a6069e88006652567334075f05755890ba0cb10a78aa5`,
over a sorted compact JSON path-to-file-hash map. Full-source/image identity is not
claimed by this focused record.
