# Engineering: exact durable artifact slice

The Local thread/process Engineering journey now publishes two pre-staged fixture
files using the production artifact operation. The registered deterministic
checker opens each published `BlobArtifactRef` through the application artifact
service, verifies its bytes and digest, fails the first content and accepts the
repaired content. The real review API records approval for the repaired reference.
After the root workspace is removed, the owner downloads the accepted artifact and
the test compares its bytes and evidence fingerprint. The same published Program
runs standalone and inside a deterministic Jira/CI/validation graph.

The final-source native Local gate passed two cases (thread and process); the
focused application/artifact/verification/architecture gate passed 41 tests.
Strict mypy on the production Engineering module and Ruff on the Engineering
source/test slice passed. The first thread attempt failed because its fixture was
outside the root-owned workspace; staging was corrected and the final gate passed.

The files are created by the test, not by a coding agent. The checker and delivery
peers are deterministic fixtures, not live CI/Jira/deployment services. The test
manually issues a namespace-scoped artifact credential into a private file, then
revokes it and removes that file; artifact grants are not yet integrated with the
root-bound managed workflow credential lifecycle. Remote isolation, replay/restart,
real external integrations and production coding-agent artifact generation remain
unproven. No paid provider or heavy remote matrix ran.

The seven Engineering source/test files have aggregate SHA-256
`1b0299d6c53163b00e2ade1bcb23d6cb569fd5fbabfface939aa9f271e1b62e8`,
over a sorted compact JSON path-to-file-hash map. This is not a full-source/image
manifest; prior native evidence describes its own historical source snapshot.
