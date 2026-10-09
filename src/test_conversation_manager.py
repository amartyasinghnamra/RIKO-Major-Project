
from conversation_manager import ConversationManager


class FakePromptManager:
    def build_prompt(self, mode="text"):
        assert mode in ("text", "voice")
        return "You are Riko, a helpful AI companion."

class FakeOllamaClient:
    def stream_response(self, messages):
        last_message = messages[-1]["content"]

        response = f"I received your message: {last_message}"

        # Simulate streaming in multiple chunks.
        yield "I received your "
        yield f"message: {last_message}"


def main():
    prompt_manager = FakePromptManager()
    ollama_client = FakeOllamaClient()

    conversation = ConversationManager(
        prompt_manager,
        ollama_client
    )

    first_response = "".join(
        conversation.stream_response(
            "My favourite subject is Operating Systems."
        )
    )

    assert "Operating Systems" in first_response

    second_response = "".join(
        conversation.stream_response(
            "What did I just tell you?"
        )
    )

    assert "What did I just tell you?" in second_response

    # System prompt + two user messages + two assistant messages.
    assert len(conversation.messages) == 5

    assert conversation.messages[0]["role"] == "system"
    assert conversation.messages[1]["role"] == "user"
    assert conversation.messages[2]["role"] == "assistant"
    assert conversation.messages[3]["role"] == "user"
    assert conversation.messages[4]["role"] == "assistant"

    print("ConversationManager test passed!")
    print("Streaming and message history verified.")


if __name__ == "__main__":
    main()
