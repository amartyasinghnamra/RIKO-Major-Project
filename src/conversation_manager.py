
class ConversationManager:
    def __init__(self, prompt_manager, ollama_client, mode="text"):
        self.ollama_client = ollama_client
        self.mode = mode

        system_prompt = prompt_manager.build_prompt(mode=mode)

        self.messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

    def stream_response(self, user_message):
        self.messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        assistant_response = []

        for chunk in self.ollama_client.stream_response(
            self.messages
        ):
            assistant_response.append(chunk)
            yield chunk

        complete_response = "".join(assistant_response)

        self.messages.append(
            {
                "role": "assistant",
                "content": complete_response,
            }
        )
