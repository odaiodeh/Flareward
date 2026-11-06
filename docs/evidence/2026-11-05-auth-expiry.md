# Workflow credential authentication expiry

Review and verification authentication previously checked expiry using only the
API process clock. A slow API clock could accept an expired grant before maintenance
revoked it. Their application-owned repository ports now support an active read;
Mongo requires both the application time and Mongo server time to precede expiry,
and rejects inconsistent decoded expiry metadata. Ordinary audit reads remain
available after expiry. This is an authentication-time check, not an atomic fence
for a request already in flight.

Focused application and architecture tests: 69 passed. Dedicated Mongo issuance
and renewal tests: 14 passed, including both purpose services with a deliberately
slow application clock. Existing real HTTP credential issuance and verification
access tests: 3 passed. Strict mypy on five production modules, Ruff lint and
format checks on eight changed Python files passed. The last typing-only guard was
added after the Mongo gate; the HTTP gate used the final source. No remote image,
Kubernetes/OpenShell or broad Temporal test ran. Full platform acceptance and
isolated receiver delivery remain unfinished.

The eight changed code/test files have aggregate SHA-256
`d8ef49cfed2b78ba793aa4a95252b6a3cd355962edb0614f09112486741743ac`, calculated
over a sorted JSON map of path to file SHA-256 at that checkpoint.

Authentication now performs another active read after observing root liveness,
rejecting a grant revoked or expired during that observation. It accepts a
concurrent bounded renewal only when the rest of the grant and credential still
match. This narrows that race; it does not make authorization atomic with later
effects. The focused application/architecture gate passed 69 cases and the final
Mongo issuance/renewal gate passed 20, exercising revoke, expiry and renewal for
both purposes. The first expanded Mongo run stopped after eight passes because the
new renewal fixture requested an expiry outside its renewal schedule; the fixture
was corrected and all 20 cases passed. Strict typing, Ruff and format checks passed.
The latest three changed files have aggregate SHA-256
`d869587a43078cd4cef0ac9ba6e90d582bfc0a592986da3e77e4fe0af254c1fb`, using the
same sorted path-to-hash format. Earlier full-source manifests remain historical.
