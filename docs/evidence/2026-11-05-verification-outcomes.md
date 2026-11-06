# Verification outcome consistency

The portable verification view validates that its outcome follows the evidence
and cancellation state attached to it. In particular, a result with missing,
failed, or errored checks cannot be labelled accepted. The service and view share
the same clock-independent outcome calculation; an incomplete, uncancelled plan
can still be pending or expired because its expiry depends on the service clock.

This is an integrity check on a representation, not an authenticity guarantee:
an untrusted producer could fabricate a whole internally consistent record. A
future Engineering Program must obtain verification and review records through
authorized services, bind them to the exact candidate and occurrence, and must not
treat arbitrary child outputs as trusted evidence. That program remains unfinished.

Verification against this source:

- `python -m pytest` on application verification/service and wait-program tests
  plus domain verification tests: 32 passed. New cases include tampered results
  arriving through the runtime invocation port.
- Dedicated local Mongo/Redis integration: the existing graph-to-reusable-waiter
  thread case passed, including API admission and trusted verifier submissions.
- Ruff lint and format checks for four changed Python files passed. Strict mypy
  with silent imported modules passed for the three changed production files.

No process, Temporal, Kubernetes/OpenShell, UI, or complete Engineering workflow
was tested in this slice. The four changed Python files have aggregate SHA-256
`f27f1ead2df6134be590857d265e4a0de02cb92bd4f64579ca1d0586aa81995b`,
calculated over a sorted compact JSON map of relative path to file SHA-256.
