"""Conversation orchestration with streamed, model-selected tool calls."""

from time import perf_counter

from src.debug_logger import log_event, log_exception
from tools.architecture_tools import ARCHITECTURE_TOOL, execute_architecture_tool

MAX_TOOL_ROUNDS = 4


class ConversationManager:
    def __init__(self, prompt_manager, ollama_client, mode="text"):
        self.ollama_client = ollama_client
        self.enable_voice_status = False
        self.messages = [{
            "role": "system",
            "content": prompt_manager.build_prompt(mode=mode),
        }]

    def _stream_and_record(self, messages):
        parts = []
        started = perf_counter()
        log_event("LLM", "STREAM_STARTED", message_count=len(messages))
        try:
            for chunk in self.ollama_client.stream_response(messages):
                parts.append(chunk)
                yield chunk
        except Exception as error:
            log_exception("LLM", "STREAM_FAILED", error)
            raise

        complete = "".join(parts)
        if complete:
            self.messages.append({"role": "assistant", "content": complete})
        log_event(
            "LLM", "STREAM_COMPLETED",
            seconds=round(perf_counter() - started, 3),
            chunks=len(parts), characters=len(complete),
        )

    def _execute_tool_calls(self, tool_calls):
        for call in tool_calls:
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name", "")
            arguments = function.get("arguments", {})

            log_event(
                "TOOLS", "TOOL_CALL_REQUESTED",
                name=name or "unknown_tool",
                arguments=arguments,
            )
            started = perf_counter()
            log_event("TOOLS", "TOOL_EXECUTION_STARTED", name=name)
            try:
                result = execute_architecture_tool(name, arguments)
            except Exception as error:
                log_exception("TOOLS", f"TOOL_EXECUTION_FAILED:{name}", error)
                result = f"Tool execution failed ({type(error).__name__})."

            log_event(
                "TOOLS", "TOOL_EXECUTION_COMPLETED",
                name=name or "unknown_tool",
                seconds=round(perf_counter() - started, 3),
                result_characters=len(str(result)),
            )
            # Ollama's chat API accepts tool results as tool-role messages.
            self.messages.append({"role": "tool", "content": str(result)})

    def stream_response(self, user_message):
        self.messages.append({"role": "user", "content": user_message})
        log_event(
            "CONVERSATION", "USER_MESSAGE_RECEIVED",
            characters=len(user_message),
        )

        stream_events = getattr(self.ollama_client, "stream_chat_events", None)
        if stream_events is None:
            # Compatibility path for existing test doubles or older clients.
            log_event("TOOLS", "STREAM_TOOL_API_UNAVAILABLE")
            yield from self._stream_and_record(self.messages)
            return

        for round_number in range(1, MAX_TOOL_ROUNDS + 1):
            if self.enable_voice_status and round_number == 1:
                yield ("__RIKO_STATUS__", "Hmm, let me think for a moment.")

            log_event(
                "TOOLS", "TOOL_SELECTION_STARTED",
                round=round_number,
            )
            assistant_parts = []
            tool_calls = []

            try:
                for event in stream_events(
                    self.messages,
                    tools=[ARCHITECTURE_TOOL],
                ):
                    event_type = event.get("type")
                    if event_type == "content":
                        chunk = event.get("content", "")
                        if chunk:
                            assistant_parts.append(chunk)
                            yield chunk
                    elif event_type == "tool_calls":
                        tool_calls = event.get("tool_calls") or []
                        if self.enable_voice_status and tool_calls:
                            yield (
                                "__RIKO_STATUS__",
                                "One moment, let me check that for you.",
                            )
                        log_event(
                            "TOOLS", "TOOL_SELECTION_COMPLETED",
                            round=round_number,
                            tool_calls=len(tool_calls),
                            seconds=event.get("seconds"),
                        )
            except Exception as error:
                log_exception("TOOLS", "TOOL_SELECTION_FAILED", error)
                raise

            if not tool_calls:
                answer = "".join(assistant_parts)
                if answer:
                    self.messages.append({
                        "role": "assistant",
                        "content": answer,
                    })
                log_event(
                    "TOOLS", "NO_TOOL_SELECTED",
                    round=round_number,
                )
                return

            # Preserve the assistant's tool-call message in the conversation.
            self.messages.append({
                "role": "assistant",
                "content": "".join(assistant_parts),
                "tool_calls": tool_calls,
            })
            self._execute_tool_calls(tool_calls)
            if self.enable_voice_status:
                yield (
                    "__RIKO_STATUS__",
                    "Got it. Let me put that together for you.",
                )
            log_event(
                "LLM", "TOOL_RESULTS_RETURNED",
                round=round_number,
            )

        log_event("TOOLS", "TOOL_ROUND_LIMIT_REACHED", limit=MAX_TOOL_ROUNDS)
        log_event("LLM", "FINAL_RESPONSE_STARTED")
        yield from self._stream_and_record(self.messages)
