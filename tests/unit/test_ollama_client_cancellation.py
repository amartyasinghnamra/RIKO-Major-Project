"""Cancellation coverage for Ollama's streamed HTTP responses."""

from __future__ import annotations

import json
import threading

from ollama_client import OllamaClient


class BlockingResponse:
    def __init__(self):
        self.closed = threading.Event()
        self.waiting = threading.Event()
        self.lines = [
            json.dumps({"message": {"content": "first"}, "done": False}).encode()
        ]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def __iter__(self):
        yield from self.lines
        self.waiting.set()
        self.closed.wait(timeout=3)
        if self.closed.is_set():
            raise OSError("response closed by cancellation")

    def close(self):
        self.closed.set()


def test_stop_response_generation_closes_active_ollama_stream():
    client = OllamaClient()
    response = BlockingResponse()
    client._post_chat = lambda *_args, **_kwargs: response
    result = []
    failures = []

    def consume():
        try:
            result.extend(client.stream_response([{"role": "user", "content": "hi"}]))
        except Exception as error:  # pragma: no cover - assertion reports details
            failures.append(error)

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert response.waiting.wait(timeout=1)

    assert client.stop_response_generation() is True
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert failures == []
    assert result == ["first"]
    assert response.closed.is_set()
    assert client._active_streams == {}


def test_stop_response_generation_cancels_tool_enabled_chat_stream():
    client = OllamaClient()
    response = BlockingResponse()
    client._post_chat = lambda *_args, **_kwargs: response
    result = []
    failures = []

    def consume():
        try:
            result.extend(
                client.stream_chat_events(
                    [{"role": "user", "content": "hi"}],
                    tools=[{"type": "function", "function": {"name": "test"}}],
                )
            )
        except Exception as error:  # pragma: no cover - assertion reports details
            failures.append(error)

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert response.waiting.wait(timeout=1)

    assert client.stop_response_generation() is True
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert failures == []
    assert result == [{"type": "content", "content": "first"}]
    assert response.closed.is_set()
    assert client._active_streams == {}
