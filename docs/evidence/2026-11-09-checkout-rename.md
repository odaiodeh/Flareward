# Flareward checkout and Git remote rename

Date: 2026-11-09. The user explicitly authorized the local repository rename
and requested a commit message afterward. No commit, staging, merge or push ran.

- GitHub serves `odaiodeh/Flareward` and redirects its former `UnifAI-ADLC` URL.
  SSH access to the renamed repository was verified before changing the remote.
- `origin` fetch/push URL is `git@github.com:odaiodeh/Flareward.git`. Remote refs
  were refreshed; `main` still tracks `origin/main`.
- The primary checkout moved atomically from
  `/Users/odaiodeh/IdeaProjects/UnifAI-ADLC` to
  `/Users/odaiodeh/IdeaProjects/Flareward`. The old folder does not remain as an alias.
- HEAD remains `5ed1cdfa832f8779da96902f63d878e66fa8266a`. Full porcelain worktree
  status matched exactly immediately before and after the move, preserving the
  existing index and uncommitted repository/feature/naming work.
- Generated Python environment paths (43 files) and Node launchers (76 files)
  were repaired. Editable core/developer/shared-support distributions were
  reinstalled from the new directory without dependency upgrades. Run Engine
  stays in its existing sibling checkout.
- The owned OpenShell gateway was healthy and had zero active sandboxes before
  stopping it. Only that gateway was recreated with its new absolute bind path,
  existing database and existing mTLS identities. Other services were left running.
- The dedicated kind kubeconfig works at its new path. The global Kubernetes
  context and other projects/clusters were not changed.

## Focused verification

CLI help and editable installation locations pass. Architecture and developer-tool
suite: **268 passed**. UI static types and actual graph/session contract runner
pass. Normal OpenShell custom operation placement: **2 passed, 8 deselected**,
covering ordinary and retained environment execution on the Local host with actual
receiver results and cleanup. Installed images were not rebuilt because application
source bytes are unchanged by the folder move. The previous broader naming gate
remains scoped to its own [record](2026-11-09-flareward-rename.md).

The [naming guide](../branding.md) and target repository tree reflect the new
checkout. Reopen `/Users/odaiodeh/IdeaProjects/Flareward` in Codex/your IDE so saved
workspace selections follow the move; application-internal project records were
not edited directly. Historical evidence keeps its original paths and hashes.
The broader ADLC goal remains paused.
