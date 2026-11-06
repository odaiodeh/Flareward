# Engineering Program: application slice

The optional `mas_plugins.engineering.program` registers a typed backend Program
through the existing application registry. It invokes an implementation child,
requests verification of its candidate identity, starts and refreshes trusted
check runners, waits for a human review after accepted verification, and invokes
a bounded repair child on failed checks or rejection. Unresolved checks/review,
closed verification/review, refused checks and exhausted repairs have explicit
non-verified outcomes. Review effect keys include the attempt number. Child
cancellation uses the existing runtime's child ownership helper.

The Program requires the registered verification/review service operation types
and their scoped provider dependencies; the canonical publication path additionally
validates each complete bundle. Trust still depends on the installed operator-owned
catalog, authenticated service, verification policy and verifiers interpreting an
actually immutable subject identity. A typed or self-consistent JSON response alone
is not evidence of authority. Git is not required by the Program contract.

Focused gate: 64 application, verification, Human Review, child contract and
architecture tests passed. Engineering scenarios exercise real in-memory application
services and deterministic check/human peers: approval, failed checks, rejected
review, bounded exhaustion, unresolved checks and review, identity substitution,
untrusted operation rejection, child cancellation and canonical publication.
Strict mypy and Ruff passed. The first publication attempt exposed a missing declared
child output binding; it was corrected before the final gate.

This does not establish native engine/API/Mongo execution, worker restart or replay,
remote placement, or embedding the same published revision in the Jira-to-deployment
workflow. No actual Jira, CI/CD, provider or human was exercised. These remain
required before calling the Engineering milestone complete.

The four changed source/test files have aggregate SHA-256
`de0e42655e1c3b987ff7546aa612795de0d5a94e8420a3047adb9a3fb5055b5a`,
over a sorted compact JSON path-to-file-hash map.
