# Direct workflow credential issuance

Review and verification issuance recheck root closure after grant registration,
including the direct non-keyed path. A confirmed closed root causes revocation
and denies issuance. If the final root observation is unavailable, an unreturned
direct grant is revoked; recoverable keyed issuance retains its reservation and
grant so the same authorized request can retry without changing credentials.

The focused application/architecture gate passed 98 tests. Dedicated MongoDB
issuance tests passed 22 cases, including both purposes and closed/unavailable
final observations. Strict mypy passed for the two changed services; Ruff lint
and formatting passed for all five changed Python files. The changed files' sorted
compact path-to-SHA-256 JSON map has SHA-256
`5da94d36b56bb033770935151ca8416df4c9a00154d7958b144230e667c0af81`.

These observations narrow the registration race; they are not an atomic fence
against root closure after the check, nor proof of cancellation or process loss
between writing a direct grant and the final check. Those recovery and lifecycle
requirements remain open. No remote execution or heavy infrastructure gate ran.
