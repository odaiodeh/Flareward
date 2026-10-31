# Historical Run Engine patches — recovery only

These files preserve the earlier local integration and unreleased active-join
prototype. Their functionality was superseded by committed SDK source at
`da10d1ac32e93a9752b9b5db1e0c71eced2f4b16`. They are not the current installation
path. **Do not apply them to that commit or a newer checkout.**

For historical reconstruction only, the original base was
`fd47e7bb6210b271be3c823e81d24e285869ddd0`, followed in this order by:

1. [Program mappings](run-engine-program-mappings.patch)
2. [Child observation](run-engine-child-observation.patch)
3. [OpenShell TLS](run-engine-openshell-tls.patch)
4. [Native run identity](run-engine-native-run-identity.patch)
5. [OpenShell policy](run-engine-openshell-policy.patch)
6. [Experimental active joins](run-engine-active-joins.patch)

The sixth patch is an incomplete prototype, not the committed SDK algorithm.
Its serialized ACTIVE policy/checkpoint layout differs from the committed layout.
Rebuild unsubmitted graphs against the committed API. Submitted prototype runs
must complete on their original compatible implementation; retain their exact
worker/receiver artifacts and histories until actual drain is verified. These
patch files alone do not prove recoverability or that any runs are drained.

See [the current integration status](../README.md) and the dated
[migration ledger](../../docs/execution-platform-migration.md) for evidence and limits.
