# Build and deploy tooling

Jenkins build/deploy pipelines retain Platform, Identity and UI only. Platform
builds require `RUN_ENGINE_SOURCE` pointing to the approved Run Engine checkout;
the root build context uses `platform/Dockerfile.dockerignore`. Deploy charts are
under `infra/helm`. Set matching API/worker host and queue settings and operator
secrets; do not deploy untested local images or rely on removed RAG/admin services.

External Jenkins/cluster execution is not part of local regression acceptance.
