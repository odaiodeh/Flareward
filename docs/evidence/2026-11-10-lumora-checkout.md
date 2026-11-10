# Lumora checkout and Git remote

Date: 2026-11-10. The user explicitly requested the Git/repository, remote and
local directory rename after the [product naming cutover](2026-11-10-lumora-rename.md).
No staging, commit, merge or push ran; the overall ADLC goal remains paused.

- GitHub's API resolves both `odaiodeh/Flareward` and `odaiodeh/Lumora` to the same
  repository identity (`1437519175`), with canonical name `odaiodeh/Lumora`.
  The hosted rename was already effective when checked; no duplicate was created.
- SSH access to `git@github.com:odaiodeh/Lumora.git` was verified. `origin` uses
  this URL for fetch/push; refs were fetched and `main` retains `origin/main` tracking.
- Checkout moved atomically from `/Users/odaiodeh/IdeaProjects/Flareward` to
  `/Users/odaiodeh/IdeaProjects/Lumora`. No old-directory symlink was left behind.
- HEAD remains `10874fe147d727d46f5552b2b203a213971de36d`. Complete null-delimited
  porcelain status, including every untracked source file, matched exactly
  immediately before/after the move. The existing index and Git history remain.
- Repaired 46 generated Python environment files and 11 Node launchers; reinstalled
  shared support/platform/developer editables from the new root without dependency
  upgrades. API/developer CLI help resolves with the new interpreter paths.
- The owned OpenShell gateway was healthy and its workspace had no sandboxes
  before stopping it. Recreated only `flareward-e2e-gateway-1` with the new absolute
  state path, original database and mTLS identities. SDK health, empty sandbox
  inventory and exact new bind mounts pass afterward. Other services were untouched.
- The owned kind node remains Ready using the kubeconfig at its new absolute path
  and explicit `kind-flareward-e2e` context. No global context or cluster was changed.

## Verification and limits

All **1,654 Python source/test files** match the earlier source manifest; moving
folders did not change application/runtime code. Focused architecture/developer
checks: **268 passed**. UI static types and actual graph/session contracts pass.
Renamed CLI help, editable locations, absence of stale launcher paths and
`git diff --check` pass. Historical evidence remains scoped to its original paths.
Current source/import names are Lumora; older Docker resource names are retained
identities, not Python compatibility packages.

This is relocation/health evidence, not application execution in Kubernetes or
OpenShell. No images were rebuilt and no remote application matrix or paid model
calls ran. The prior namespace cutover's full core/native/UI verification remains
recorded separately; it does not certify current receiver images. Reopen the new
Lumora folder in Codex/IDE; application-internal project databases were not edited.
