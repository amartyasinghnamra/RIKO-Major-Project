"""Conversation orchestration with streamed, model-selected tool calls."""

import inspect
import json
import re
import threading
from time import perf_counter

from src.debug_logger import log_event, log_exception
from src.tools.architecture_tools import (
    ARCHITECTURE_TOOL,
    TOPIC_FILES,
    execute_architecture_tool,
)
from src.tools.codebase_explorer import CODEBASE_TOOL, execute_codebase_tool

MAX_TOOL_ROUNDS = 4


class ConversationManager:
    def __init__(self, prompt_manager, ollama_client, mode="text"):
        self.ollama_client = ollama_client
        self.enable_voice_status = False
        self.enable_text_status = False
        self._response_lock = threading.Lock()
        self._response_cancel_event = threading.Event()
        self._response_active = False
        self.messages = [{
            "role": "system",
            "content": prompt_manager.build_prompt(mode=mode),
        }]

    def begin_response(self):
        """Prepare a cancellable response before a UI enables its Stop button."""
        with self._response_lock:
            if not self._response_active:
                self._response_cancel_event = threading.Event()
                self._response_active = True
            return self._response_cancel_event

    def stop_response_generation(self) -> bool:
        """Stop model generation and close any active Ollama stream."""
        with self._response_lock:
            if not self._response_active:
                return False
            cancel_event = self._response_cancel_event
            cancel_event.set()

        stop_client = getattr(self.ollama_client, "stop_response_generation", None)
        if callable(stop_client):
            stop_client()
        return True

    def _finish_response(self, cancel_event) -> None:
        with self._response_lock:
            if cancel_event is self._response_cancel_event:
                self._response_active = False

    @staticmethod
    def _supports_cancel_event(method) -> bool:
        try:
            parameters = inspect.signature(method).parameters.values()
        except (TypeError, ValueError):
            return False
        return any(
            parameter.name == "cancel_event"
            or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )

    def _client_stream(self, method, *args, cancel_event, **kwargs):
        if self._supports_cancel_event(method):
            kwargs["cancel_event"] = cancel_event
        return method(*args, **kwargs)

    @staticmethod
    def _tool_result_paths(name, arguments, result):
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}

        if name == "get_architecture_info":
            topic = arguments.get("topic")
            topic_file = TOPIC_FILES.get(topic)
            if topic_file and not any(
                marker in result
                for marker in ("is missing", "Could not read")
            ):
                return [f"knowledge/architecture/{topic_file[0]}"]
            return []

        if name != "explore_codebase":
            return []

        operation = arguments.get("operation")
        if operation == "read_file":
            match = re.match(r"^Source: ([^\r\n]+)", result)
            return [match.group(1)] if match else []
        if operation == "list_files" and result.startswith("Project-relative files:\n"):
            return [
                line for line in result.splitlines()[1:]
                if line and not line.startswith(("[", "("))
            ]
        if operation == "search_code":
            paths = []
            for line in result.splitlines():
                match = re.match(r"^(.+?):\d+:\s", line)
                if match and match.group(1) not in paths:
                    paths.append(match.group(1))
            return paths
        return []

    def _stream_and_record(self, messages, cancel_event):
        parts = []
        started = perf_counter()
        log_event("LLM", "STREAM_STARTED", message_count=len(messages))
        try:
            stream = self._client_stream(
                self.ollama_client.stream_response,
                messages,
                cancel_event=cancel_event,
            )
            for chunk in stream:
                if cancel_event.is_set():
                    break
                parts.append(chunk)
                yield chunk
        except Exception as error:
            log_exception("LLM", "STREAM_FAILED", error)
            raise

        complete = "".join(parts)
        if complete and not cancel_event.is_set():
            self.messages.append({"role": "assistant", "content": complete})
        log_event(
            "LLM", "STREAM_COMPLETED",
            seconds=round(perf_counter() - started, 3),
            chunks=len(parts), characters=len(complete),
        )

    def _execute_tool_calls(self, tool_calls, cancel_event=None):
        for call in tool_calls:
            if cancel_event is not None and cancel_event.is_set():
                return
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
                if name == "get_architecture_info":
                    result = execute_architecture_tool(name, arguments)
                elif name == "explore_codebase":
                    result = execute_codebase_tool(name, arguments)
                else:
                    result = f"Tool '{name or 'unknown_tool'}' is not available."
            except Exception as error:
                log_exception("TOOLS", f"TOOL_EXECUTION_FAILED:{name}", error)
                result = f"Tool execution failed ({type(error).__name__})."

            if cancel_event is not None and cancel_event.is_set():
                return

            log_event(
                "TOOLS", "TOOL_EXECUTION_COMPLETED",
                name=name or "unknown_tool",
                seconds=round(perf_counter() - started, 3),
                result_characters=len(str(result)),
            )
            # Ollama's chat API accepts tool results as tool-role messages.
            self.messages.append({"role": "tool", "content": str(result)})
            yield (
                "__RIKO_TOOL__",
                {
                    "tool_name": name or "unknown_tool",
                    "arguments": arguments,
                    "result_paths": self._tool_result_paths(
                        name,
                        arguments,
                        str(result),
                    ),
                },
            )

    def stream_response(self, user_message):
        cancel_event = self.begin_response()
        try:
            yield from self._stream_response(user_message, cancel_event)
        finally:
            self._finish_response(cancel_event)

    def _stream_response(self, user_message, cancel_event):
        self.messages.append({"role": "user", "content": user_message})
        log_event(
            "CONVERSATION", "USER_MESSAGE_RECEIVED",
            characters=len(user_message),
        )

        stream_events = getattr(self.ollama_client, "stream_chat_events", None)
        if stream_events is None:
            # Compatibility path for existing test doubles or older clients.
            log_event("TOOLS", "STREAM_TOOL_API_UNAVAILABLE")
            yield from self._stream_and_record(self.messages, cancel_event)
            return

        for round_number in range(1, MAX_TOOL_ROUNDS + 1):
            if cancel_event.is_set():
                return
            log_event(
                "TOOLS", "TOOL_SELECTION_STARTED",
                round=round_number,
            )
            assistant_parts = []
            tool_calls = []

            try:
                stream = self._client_stream(
                    stream_events,
                    self.messages,
                    cancel_event=cancel_event,
                    tools=[ARCHITECTURE_TOOL, CODEBASE_TOOL],
                )
                for event in stream:
                    if cancel_event.is_set():
                        return
                    event_type = event.get("type")
                    if event_type == "content":
                        chunk = event.get("content", "")
                        if chunk:
                            assistant_parts.append(chunk)
                            yield chunk
                    elif event_type == "tool_calls":
                        tool_calls = event.get("tool_calls") or []
                        if (self.enable_voice_status or self.enable_text_status) and tool_calls:
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

            if cancel_event.is_set():
                return

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
            yield from self._execute_tool_calls(tool_calls, cancel_event)
            if cancel_event.is_set():
                return
            if self.enable_voice_status or self.enable_text_status:
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
        yield from self._stream_and_record(self.messages, cancel_event)
