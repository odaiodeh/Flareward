# CI ownership

Builds package retained apps; deployment consumes explicit image versions and
`infra/helm` release groups. Platform API and worker use the same artifact. Named
Run Engine build inputs are required; provider credentials remain external secrets.
See [the tooling guide](README.md) and the platform's package/image test commands.
