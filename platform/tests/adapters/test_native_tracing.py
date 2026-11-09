"""Real OTLP export retains isolation and drains owned resources through cancellation."""

import asyncio
import base64
import threading
from contextlib import contextmanager
from hashlib import sha256

import pytest
from opentelemetry import trace
from pydantic import SecretStr, ValidationError
from runengine.invocation.errors import InvocationInfrastructureError
from support.telemetry import span_attributes, trace_collector

from flareward.bootstrap import tracing as tracing_bootstrap
from flareward.bootstrap.settings.receiver_settings import ReceiverSettings
from flareward.bootstrap.tracing import receiver_tracing
from flareward.services.tracing.adapters.langfuse import otel


def tracing_settings(base_url):
    return ReceiverSettings(
        interactions="disabled",
        tracing="langfuse",
        langfuse_base_url=base_url,
        langfuse_public_key=SecretStr("trace-public"),
        langfuse_secret_key=SecretStr("trace-private"),
    )


async def test_concurrent_owners_export_correlated_nested_spans_without_global_provider():
    original = trace.get_tracer_provider()
    processors = {thread for thread in threading.enumerate() if thread.name.startswith("OtelBatch")}
    async with trace_collector() as collector:
        settings = tracing_settings(collector.base_url)
        async with receiver_tracing(settings) as second:
            async with receiver_tracing(settings) as first:
                with first.trace_session("one", "alice", {"execution_id": "first"}):
                    with first.trace_llm(
                        "fixture", "provider", [{"secret": SecretStr("masked-value")}]
                    ) as handle:
                        handle.update(output="answer", usage_details={"input": 2, "output": 3})
                await asyncio.to_thread(first.flush)
            with second.trace_session("two", "alice"):
                with second.trace_tool("after-first-owner-closed"):
                    pass
        # Closing one owner cannot disable a later owner with the same credentials.
        async with receiver_tracing(settings) as later:

            async def record(service, session):
                with service.trace_session(session, "alice", {"execution_id": session}):
                    await asyncio.sleep(0)
                    with service.trace_tool("echo", {"session": session}) as handle:
                        handle.update(output=object())

            await asyncio.gather(record(later, "three"), record(later, "four"))
        spans = collector.spans
        assert len(spans) == 8
        for span in spans:
            attributes = span_attributes(span)
            assert span.trace_id.hex() == sha256(attributes["session.id"].encode()).hexdigest()[:32]
            assert attributes["user.id"] == "alice"
        llm = next(span for span in spans if span.name == "provider/fixture")
        assert (
            span_attributes(llm)["langfuse.observation.usage_details"] == '{"input":2,"output":3}'
        )
        assert all(b"masked-value" not in span.SerializeToString() for span in spans)
        assert all(
            batch.path == "/api/public/otel/v1/traces" and batch.ingestion_version == "4"
            for batch in collector.batches
        )
        assert all(
            batch.authorization
            == "Basic " + base64.b64encode(b"trace-public:trace-private").decode()
            for batch in collector.batches
        )
        assert trace.get_tracer_provider() is original
        assert {
            thread for thread in threading.enumerate() if thread.name.startswith("OtelBatch")
        } == processors


async def test_cancellation_waits_for_pending_export_then_closes_owner():
    async with trace_collector() as collector:
        collector.allow_responses.clear()

        async def invoke():
            async with receiver_tracing(tracing_settings(collector.base_url)) as tracing:
                with tracing.trace_session("cancelled", "alice"):
                    with tracing.trace_tool("write"):
                        pass

        task = asyncio.create_task(invoke())
        assert await asyncio.to_thread(collector.received.wait, 5)
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done()
        collector.allow_responses.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(collector.spans) == 2


async def test_cancelled_acquisition_closes_the_resource_created_after_cancellation(monkeypatch):
    created, release, closed = threading.Event(), threading.Event(), threading.Event()
    factory = otel.owned_tracing

    @contextmanager
    def held_factory(**configuration):
        with factory(**configuration) as tracing:
            created.set()
            assert release.wait(timeout=5)
            try:
                yield tracing
            finally:
                closed.set()

    monkeypatch.setattr(otel, "owned_tracing", held_factory)
    async with trace_collector() as collector:

        async def invoke():
            async with receiver_tracing(tracing_settings(collector.base_url)):
                pytest.fail("A cancelled acquisition must not run application work")

        task = asyncio.create_task(invoke())
        try:
            assert await asyncio.to_thread(created.wait, 5)
            task.cancel()
            await asyncio.sleep(0.05)
            assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set()


async def test_missing_optional_adapter_is_a_private_infrastructure_failure(monkeypatch):
    def unavailable(name):
        raise ModuleNotFoundError("private-import-diagnostic")

    monkeypatch.setattr(tracing_bootstrap, "import_module", unavailable)
    with pytest.raises(InvocationInfrastructureError) as error:
        async with receiver_tracing(tracing_settings("http://localhost:4318")):
            pytest.fail("The missing adapter must fail before application work")
    assert not error.value.retryable
    assert "private-import-diagnostic" not in str(error.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"langfuse_secret_key": ""},
        {"tracing_timeout": 0},
        {"langfuse_base_url": "http://user:private@localhost"},
    ],
)
def test_invalid_local_tracing_configuration_is_rejected(changes):
    values = tracing_settings("http://localhost:4318").model_dump(mode="python")
    with pytest.raises(ValidationError):
        ReceiverSettings.model_validate({**values, **changes})
