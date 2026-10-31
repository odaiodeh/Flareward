"""Invocation-owned OTLP tracing; no global provider or Langfuse SDK singleton."""

import base64
import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from hashlib import sha256
from typing import Any

from mas.core.tracing import ObservationHandle, TracingService
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.trace import Span, StatusCode
from pydantic_core import PydanticSerializationError, to_json

logger = logging.getLogger(__name__)


class _SessionIds(RandomIdGenerator):
    def __init__(self) -> None:
        self.seed: ContextVar[str] = ContextVar("unifai_trace_seed", default="")

    def generate_trace_id(self) -> int:
        seed = self.seed.get()
        return (
            int.from_bytes(sha256(seed.encode()).digest()[:16])
            if seed
            else super().generate_trace_id()
        )


class LangfuseOtelTracingService(TracingService):
    """Own the supplied exporter and a private provider until ``close`` drains them."""

    def __init__(self, exporter: SpanExporter, *, timeout_seconds: float = 5) -> None:
        self._timeout_ms = int(timeout_seconds * 1000)
        self._ids = _SessionIds()
        self._attributes: ContextVar[dict[str, str]] = ContextVar(
            "unifai_trace_attributes", default={}
        )
        self._provider = TracerProvider(
            id_generator=self._ids,
            resource=Resource.create({"service.name": "unifai-receiver"}),
            shutdown_on_exit=False,
        )
        self._provider.add_span_processor(
            BatchSpanProcessor(exporter, export_timeout_millis=self._timeout_ms)
        )
        self._tracer = self._provider.get_tracer("unifai.mas")

    @property
    def enabled(self) -> bool:
        return True

    @contextmanager
    def _observe(
        self,
        name: str,
        *,
        kind: str = "span",
        context: Context | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Iterator[ObservationHandle]:
        with self._tracer.start_as_current_span(
            name,
            context=context,
            attributes={
                **self._attributes.get(),
                "langfuse.observation.type": kind,
                **(attributes or {}),
            },
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield ObservationHandle(lambda **values: _update(span, **values))
            except BaseException as error:
                # Exception strings can contain resolved credentials. Keep classification only.
                span.set_status(StatusCode.ERROR)
                span.set_attribute("langfuse.observation.status_message", type(error).__name__)
                raise

    @contextmanager
    def trace_session(
        self, session_id: str, user_id: str = "", metadata: dict[str, Any] | None = None
    ) -> Iterator[ObservationHandle]:
        attributes = {
            "session.id": session_id,
            "user.id": user_id,
            "langfuse.trace.name": f"session:{session_id}",
            **_metadata("langfuse.trace.metadata", metadata),
        }
        seed = self._ids.seed.set(session_id)
        token = self._attributes.set(attributes)
        try:
            # A receiver root must not inherit a previous execution's ambient span.
            with self._observe(f"session:{session_id}", context=Context()) as handle:
                yield handle
        finally:
            self._attributes.reset(token)
            self._ids.seed.reset(seed)

    def trace_node(
        self, node_uid: str, node_type: str, display_name: str = ""
    ) -> AbstractContextManager[ObservationHandle]:
        return self._observe(
            display_name or node_uid,
            attributes=_metadata(
                "langfuse.observation.metadata", {"node_uid": node_uid, "node_type": node_type}
            ),
        )

    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationHandle]:
        return self._observe(
            f"{provider}/{model}",
            kind="generation",
            attributes={
                "langfuse.observation.model.name": model,
                "langfuse.observation.input": _json(input_messages),
                **_metadata(
                    "langfuse.observation.metadata", {**(metadata or {}), "provider": provider}
                ),
            },
        )

    def trace_tool(
        self, tool_name: str, tool_input: dict[str, Any] | None = None
    ) -> AbstractContextManager[ObservationHandle]:
        return self._observe(
            f"tool:{tool_name}",
            kind="tool",
            attributes={"langfuse.observation.input": _json(tool_input)},
        )

    def trace_agent_iteration(
        self, iteration: int, strategy: str = ""
    ) -> AbstractContextManager[ObservationHandle]:
        return self._observe(
            f"iteration:{iteration}",
            attributes=_metadata(
                "langfuse.observation.metadata", {"iteration": iteration, "strategy": strategy}
            ),
        )

    def flush(self) -> None:
        if not self._provider.force_flush(timeout_millis=self._timeout_ms):
            logger.warning("Tracing export did not finish before its flush deadline")

    def close(self) -> None:
        self._provider.shutdown()


def _metadata(prefix: str, values: dict[str, Any] | None) -> dict[str, str]:
    return {
        f"{prefix}.{name}": value if isinstance(value, str) else _json(value)
        for name, value in (values or {}).items()
    }


def _update(span: Span, **values: Any) -> None:
    for name, value in values.items():
        if value is None:
            continue
        if name == "metadata":
            span.set_attributes(_metadata("langfuse.observation.metadata", value))
        else:
            span.set_attribute(
                f"langfuse.observation.{name}",
                value if name in {"level", "status_message"} else _json(value),
            )
    if values.get("level") == "ERROR":
        span.set_status(StatusCode.ERROR)


def _json(value: Any) -> str:
    try:
        return to_json(value).decode()
    except PydanticSerializationError, TypeError, ValueError:
        return to_json({"unavailable_type": type(value).__name__}).decode()


@contextmanager
def owned_tracing(
    *, public_key: str, secret_key: str, base_url: str, timeout_seconds: float
) -> Iterator[TracingService]:
    authorization = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    exporter: SpanExporter = OTLPSpanExporter(
        endpoint=base_url.rstrip("/") + "/api/public/otel/v1/traces",
        headers={"Authorization": "Basic " + authorization, "x-langfuse-ingestion-version": "4"},
        timeout=timeout_seconds,
    )
    try:
        service = LangfuseOtelTracingService(exporter, timeout_seconds=timeout_seconds)
    except BaseException:
        exporter.shutdown()
        raise
    try:
        yield service
    finally:
        service.close()
