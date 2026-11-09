"""In-memory HTTP responses exercise real LLM SDK parsing without model calls."""

import asyncio
import json
from dataclasses import dataclass, field
from enum import StrEnum

import httpx


class LLMProtocol(StrEnum):
    GEMINI = "gemini"
    RESPONSES = "responses"
    COMPLETIONS = "completions"


@dataclass
class ModelWire:
    protocol: LLMProtocol
    tool_call: bool = False
    fail: bool = False
    pause: bool = False
    requests: list[httpx.Request] = field(default_factory=list)
    streams: list[ModelStream] = field(default_factory=list)
    waiting: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        streaming = body.get("stream") or "streamGenerateContent" in request.url.path
        if streaming:
            stream = ModelStream(self)
            self.streams.append(stream)
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)
        if self.fail:
            raise RuntimeError("private-provider-diagnostic")
        return httpx.Response(200, json=self.response())

    def response(self) -> dict:
        if self.protocol == LLMProtocol.GEMINI:
            part = (
                {"functionCall": {"name": "evidence", "args": {"value": 7}}}
                if self.tool_call
                else {"text": "hello world"}
            )
            return {"candidates": [{"content": {"role": "model", "parts": [part]}}]}
        if self.protocol == LLMProtocol.RESPONSES:
            item = (
                {
                    "type": "function_call",
                    "id": "fc",
                    "call_id": "call",
                    "name": "evidence",
                    "arguments": '{"value":7}',
                    "status": "completed",
                }
                if self.tool_call
                else {
                    "type": "message",
                    "id": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "hello world", "annotations": []}],
                }
            )
            return {
                "id": "response",
                "object": "response",
                "created_at": 1,
                "model": "fixture",
                "output": [item],
                "usage": None,
            }
        message = {"role": "assistant", "content": "hello world"}
        if self.tool_call:
            message["tool_calls"] = [
                {
                    "id": "call",
                    "type": "function",
                    "function": {"name": "evidence", "arguments": '{"value":7}'},
                }
            ]
        return {
            "id": "completion",
            "object": "chat.completion",
            "created": 1,
            "model": "fixture",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": None,
        }

    def event(self, text: str) -> bytes:
        if self.protocol == LLMProtocol.GEMINI:
            value = {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}
        elif self.protocol == LLMProtocol.RESPONSES:
            value = {
                "type": "response.output_text.delta",
                "delta": text,
                "item_id": "message",
                "output_index": 0,
                "content_index": 0,
                "sequence_number": 1,
                "logprobs": [],
            }
        else:
            value = {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "fixture",
                "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
            }
        return f"data: {json.dumps(value)}\n\n".encode()


class ModelStream(httpx.AsyncByteStream):
    def __init__(self, wire: ModelWire) -> None:
        self.wire = wire
        self.closed = False

    async def __aiter__(self):
        yield self.wire.event("hello ")
        if self.wire.pause:
            self.wire.waiting.set()
            await self.wire.release.wait()
        if self.wire.fail:
            raise RuntimeError("private-provider-diagnostic")
        yield self.wire.event("world")

    async def aclose(self) -> None:
        self.closed = True
