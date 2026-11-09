# Build with the approved Run Engine checkout as a named source context.
ARG PLATFORM_BASE=python:3.14-slim
FROM ${PLATFORM_BASE}

ARG INSTALL_GIT=false
RUN if [ "${INSTALL_GIT}" = "true" ] && ! command -v git >/dev/null; then \
      apt-get update && apt-get install -y --no-install-recommends git \
      && rm -rf /var/lib/apt/lists/*; \
    fi

ARG RUN_ENGINE_EXTRAS=temporal
ARG PLATFORM_EXTRAS=api,credentials,blueprints,temporal,telemetry
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY --from=run_engine /pyproject.toml /opt/run-engine/pyproject.toml
COPY --from=run_engine /README.md /opt/run-engine/README.md
COPY --from=run_engine /src/ /opt/run-engine/src/
COPY packages/service-support/pyproject.toml /opt/service-support/pyproject.toml
COPY packages/service-support/src/ /opt/service-support/src/
COPY platform/pyproject.toml /opt/flareward/pyproject.toml
COPY platform/src/ /opt/flareward/src/
RUN pip install --no-cache-dir "/opt/run-engine[${RUN_ENGINE_EXTRAS}]" /opt/service-support "/opt/flareward[${PLATFORM_EXTRAS}]"

# No test fixtures, private credentials, operator policies or local environments
# are copied. Supply deployment configuration and private bindings at runtime.
RUN chown 1000:1000 /app
USER 1000:1000
EXPOSE 13457
ENTRYPOINT ["flareward-platform"]
CMD ["serve", "--host", "0.0.0.0", "--port", "13457"]
