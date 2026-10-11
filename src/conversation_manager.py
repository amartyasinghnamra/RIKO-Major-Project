from tools.architecture_tools import (
    ARCHITECTURE_TOOL,
    execute_architecture_tool,
    should_offer_architecture_tool,
)


class ConversationManager:
    def __init__(self, prompt_manager, ollama_client, mode="text"): 
        self.ollama_client = ollama_client
        self.messages = [{
            "role": "system",
            "content": prompt_manager.build_prompt(),
        }]

    def _stream_and_record(self, messages):
        parts = []
        for chunk in self.ollama_client.stream_response(messages):
            parts.append(chunk)
            yield chunk
        complete = "".join(parts)
        if complete:
            self.messages.append({"role": "assistant", "content": complete})

    def _architecture_response(self):
        tool_message = self.ollama_client.chat_once(
            self.messages,
            tools=[ARCHITECTURE_TOOL],
        )
        tool_calls = tool_message.get("tool_calls") or []

        if not tool_calls:
            answer = tool_message.get("content", "")
            if answer:
                self.messages.append({"role": "assistant", "content": answer})
                yield answer
            return

        self.messages.append({
            "role": "assistant",
            "content": tool_message.get("content", ""),
            "tool_calls": tool_calls,
        })

        for call in tool_calls:
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name", "")
            arguments = function.get("arguments", {})
            result = execute_architecture_tool(name, arguments)
            self.messages.append({
                "role": "tool",
                "tool_name": name or "unknown_tool",
                "content": result,
            })

        # The final response is streamed normally; tool-call JSON is never spoken.
        yield from self._stream_and_record(self.messages)

    def stream_response(self, user_message):
        self.messages.append({"role": "user", "content": user_message})
        if should_offer_architecture_tool(user_message, self.messages[:-1]):
            yield from self._architecture_response()
        else:
            yield from self._stream_and_record(self.messages)
