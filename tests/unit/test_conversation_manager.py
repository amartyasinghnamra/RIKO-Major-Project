import threading

from conversation_manager import ConversationManager


class FakePromptManager:
    def __init__(self):
        self.requested_modes = []

    def build_prompt(self, mode="text"):
        assert mode in ("text", "voice")
        self.requested_modes.append(mode)
        return f"Prompt for {mode} mode."


class FakeOllamaClient:
    def stream_response(self, messages):
        last_message = messages[-1]["content"]
        yield "I received your "
        yield f"message: {last_message}"


def test_streaming_and_conversation_history():
    conversation = ConversationManager(
        FakePromptManager(), FakeOllamaClient()
    )

    first = "".join(
        conversation.stream_response(
            "My favourite subject is Operating Systems."
        )
    )
    second = "".join(
        conversation.stream_response("What did I just tell you?")
    )

    assert "Operating Systems" in first
    assert "What did I just tell you?" in second
    assert len(conversation.messages) == 5
    assert [m["role"] for m in conversation.messages] == [
        "system", "user", "assistant", "user", "assistant"
    ]


def test_text_and_voice_prompt_modes():
    prompts = FakePromptManager()
    client = FakeOllamaClient()

    text = ConversationManager(prompts, client, mode="text")
    voice = ConversationManager(prompts, client, mode="voice")

    assert prompts.requested_modes == ["text", "voice"]
    assert text.messages[0]["content"] == "Prompt for text mode."
    assert voice.messages[0]["content"] == "Prompt for voice mode."


def test_stop_response_generation_stops_the_stream_and_discards_partial_history():
    started = threading.Event()

    class CancellableClient:
        def stream_chat_events(self, _messages, *, tools=None, cancel_event=None):
            yield {"type": "content", "content": "partial answer"}
            started.set()
            while not cancel_event.wait(timeout=0.01):
                pass

    conversation = ConversationManager(FakePromptManager(), CancellableClient())
    conversation.begin_response()
    collected = []
    worker = threading.Thread(
        target=lambda: collected.extend(conversation.stream_response("hello")),
        daemon=True,
    )
    worker.start()

    assert started.wait(timeout=1)
    assert conversation.stop_response_generation() is True
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert collected == ["partial answer"]
    assert conversation.messages[-1] == {"role": "user", "content": "hello"}
    assert conversation.stop_response_generation() is False


def test_tool_call_emits_structured_event_with_result_paths_and_final_text():
    class ToolCallingClient:
        def __init__(self):
            self.calls = 0

        def stream_chat_events(self, messages, *, tools=None, cancel_event=None):
            self.calls += 1
            if self.calls == 1:
                yield {
                    "type": "tool_calls",
                    "tool_calls": [{
                        "function": {
                            "name": "get_architecture_info",
                            "arguments": {"topic": "modules", "detail": "full"},
                        },
                    }],
                }
            else:
                assert any(
                    message.get("role") == "tool"
                    and "knowledge/architecture/modules.md" in message.get("content", "")
                    for message in messages
                )
                yield {"type": "content", "content": "Here is the architecture."}

    conversation = ConversationManager(FakePromptManager(), ToolCallingClient())
    events = list(conversation.stream_response("Explain the modules"))

    tool_events = [
        event[1]
        for event in events
        if isinstance(event, tuple)
        and len(event) == 2
        and event[0] == "__RIKO_TOOL__"
    ]
    assert tool_events == [{
        "tool_name": "get_architecture_info",
        "arguments": {"topic": "modules", "detail": "full"},
        "result_paths": ["knowledge/architecture/modules.md"],
    }]
    assert "Here is the architecture." in events
