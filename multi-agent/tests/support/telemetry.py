"""An owned OTLP HTTP endpoint records real protobuf transport without a vendor account."""

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mas.core.async_work import await_owned
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.trace.v1.trace_pb2 import Span


@dataclass(frozen=True)
class TraceBatch:
    path: str
    authorization: str
    ingestion_version: str
    spans: tuple[Span, ...]


class TraceCollector:
    def __init__(self) -> None:
        self._batches: list[TraceBatch] = []
        self._lock = threading.Lock()
        self.received = threading.Event()
        self.allow_responses = threading.Event()
        self.allow_responses.set()
        self.response_status = 200
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                request = ExportTraceServiceRequest.FromString(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
                batch = TraceBatch(
                    self.path,
                    self.headers["Authorization"],
                    self.headers["x-langfuse-ingestion-version"],
                    tuple(
                        span
                        for resource in request.resource_spans
                        for scope in resource.scope_spans
                        for span in scope.spans
                    ),
                )
                with collector._lock:
                    collector._batches.append(batch)
                collector.received.set()
                collector.allow_responses.wait(timeout=10)
                self.send_response(collector.response_status)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    @property
    def port(self) -> int:
        return self._server.server_port

    @property
    def batches(self) -> list[TraceBatch]:
        with self._lock:
            return list(self._batches)

    @property
    def spans(self) -> tuple[Span, ...]:
        return tuple(span for batch in self.batches for span in batch.spans)

    def close(self) -> None:
        self.allow_responses.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        assert not self._thread.is_alive()


@asynccontextmanager
async def trace_collector() -> AsyncIterator[TraceCollector]:
    collector = TraceCollector()
    try:
        yield collector
    finally:
        await await_owned(asyncio.to_thread(collector.close))


def span_attributes(span: Span) -> dict[str, str]:
    return {attribute.key: attribute.value.string_value for attribute in span.attributes}
