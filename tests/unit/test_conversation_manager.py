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
