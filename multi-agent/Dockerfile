# Build with the approved Run Engine checkout as a named source context.
ARG PLATFORM_BASE=python:3.14-slim
FROM ${PLATFORM_BASE}

ARG RUN_ENGINE_EXTRAS=temporal
ARG MAS_EXTRAS=api,credentials,blueprints,temporal,telemetry
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY --from=run_engine /pyproject.toml /opt/run-engine/pyproject.toml
COPY --from=run_engine /README.md /opt/run-engine/README.md
COPY --from=run_engine /src/ /opt/run-engine/src/
COPY global_utils/pyproject.toml /opt/global-utils/pyproject.toml
COPY global_utils/src/ /opt/global-utils/src/
COPY multi-agent/pyproject.toml /opt/mas/pyproject.toml
COPY multi-agent/lib/ /opt/mas/lib/
COPY multi-agent/adapters/ /opt/mas/adapters/
COPY multi-agent/bootstrap/ /opt/mas/bootstrap/
COPY multi-agent/config/ /opt/mas/config/
COPY multi-agent/plugins/ /opt/mas/plugins/
RUN pip install --no-cache-dir "/opt/run-engine[${RUN_ENGINE_EXTRAS}]" /opt/global-utils "/opt/mas[${MAS_EXTRAS}]"

# No test fixtures, private credentials, operator policies or local environments
# are copied. Supply deployment configuration and private bindings at runtime.
RUN chown 1000:1000 /app
USER 1000:1000
EXPOSE 13457
ENTRYPOINT ["mas-platform"]
CMD ["serve", "--host", "0.0.0.0", "--port", "13457"]
