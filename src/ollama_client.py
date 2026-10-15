import json
import threading
from time import perf_counter
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class OllamaClient:
    def __init__(
        self,
        model="qwen3:4b-instruct",
        base_url="http://127.0.0.1:11434",
        keep_alive="60m",
    ):
        self.model = model
        self.chat_url = f"{base_url.rstrip('/')}/api/chat"
        self.keep_alive = keep_alive
        self._active_streams = {}
        self._active_streams_lock = threading.Lock()

    def stop_response_generation(self) -> bool:
        """Cancel the active streamed request and close its HTTP response."""
        with self._active_streams_lock:
            active = list(self._active_streams.values())

        for response, cancel_event in active:
            cancel_event.set()
            try:
                response.close()
            except Exception:
                pass
        return bool(active)

    def _register_stream(self, response, cancel_event=None):
        cancel_event = cancel_event or threading.Event()
        response_id = id(response)
        with self._active_streams_lock:
            self._active_streams[response_id] = (response, cancel_event)
        if cancel_event.is_set():
            try:
                response.close()
            except Exception:
                pass
        return response_id, cancel_event

    def _unregister_stream(self, response_id):
        with self._active_streams_lock:
            self._active_streams.pop(response_id, None)

    def _post_chat(self, messages, *, stream, options=None, tools=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
        }
        if options is not None:
            payload["options"] = options
        if tools:
            payload["tools"] = tools

        request = Request(
            self.chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urlopen(request, timeout=120)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            message = f"Ollama returned HTTP error {error.code}"
            if detail:
                message += f": {detail}"
            raise RuntimeError(message) from error
        except URLError as error:
            raise RuntimeError(
                "Could not connect to Ollama. Check that Ollama is running."
            ) from error

    def chat_once(self, messages, *, tools=None, options=None):
        """Return one complete assistant message, including any tool calls."""
        with self._post_chat(
            messages, stream=False, options=options, tools=tools
        ) as response:
            try:
                data = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError("Ollama returned an invalid chat response.") from error

        message = data.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama response did not contain an assistant message.")
        return message

    def warm_up(self, system_prompt):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Reply with exactly: Ready."},
        ]
        started = perf_counter()
        with self._post_chat(
            messages, stream=False, options={"num_predict": 1}
        ) as response:
            response.read()
        return perf_counter() - started

    def stream_response(
        self,
        messages,
        *,
        on_first_token=None,
        on_metrics=None,
        cancel_event=None,
    ):
        """Stream assistant text; tool-enabled requests use chat_once first."""
        started = perf_counter()
        first_token_seconds = None
        response = self._post_chat(messages, stream=True)
        response_id, request_cancel = self._register_stream(response, cancel_event)
        try:
            with response:
                for line in response:
                    if request_cancel.is_set():
                        return
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise RuntimeError(
                            "Ollama returned an invalid streaming response."
                        ) from error

                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        if first_token_seconds is None:
                            first_token_seconds = perf_counter() - started
                            if on_first_token is not None:
                                on_first_token(first_token_seconds)
                        yield chunk

                    if data.get("done", False):
                        if on_metrics is not None:
                            on_metrics({
                                "time_to_first_token_seconds": first_token_seconds,
                                "total_seconds": perf_counter() - started,
                                "prompt_eval_count": data.get("prompt_eval_count"),
                                "prompt_eval_duration_ns": data.get("prompt_eval_duration"),
                                "eval_count": data.get("eval_count"),
                                "eval_duration_ns": data.get("eval_duration"),
                                "load_duration_ns": data.get("load_duration"),
                                "total_duration_ns": data.get("total_duration"),
                            })
                        break
        except Exception:
            if not request_cancel.is_set():
                raise
        finally:
            self._unregister_stream(response_id)


    def stream_chat_events(self, messages, *, tools=None, cancel_event=None):
        """Yield streamed text events and a final aggregated tool-call event."""
        started = perf_counter()
        tool_calls = {}
        response = self._post_chat(messages, stream=True, tools=tools)
        response_id, request_cancel = self._register_stream(response, cancel_event)
        try:
            with response:
                for line in response:
                    if request_cancel.is_set():
                        return
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise RuntimeError(
                            "Ollama returned an invalid streaming response."
                        ) from error

                    message = data.get("message", {})
                    content = message.get("content", "")
                    if content:
                        yield {"type": "content", "content": content}

                    for position, call in enumerate(message.get("tool_calls") or []):
                        if not isinstance(call, dict):
                            continue
                        index = call.get("index", position)
                        current = tool_calls.setdefault(index, {
                            "type": "function",
                            "function": {"name": "", "arguments": {}},
                        })
                        function = call.get("function") or {}
                        name = function.get("name")
                        if name:
                            current["function"]["name"] = name

                        arguments = function.get("arguments")
                        if isinstance(arguments, dict):
                            current["function"]["arguments"].update(arguments)
                        elif isinstance(arguments, str):
                            # Some streaming backends send arguments as JSON text.
                            try:
                                parsed = json.loads(arguments)
                                if isinstance(parsed, dict):
                                    current["function"]["arguments"].update(parsed)
                            except json.JSONDecodeError:
                                current["function"]["arguments_raw"] = arguments

                    if data.get("done", False):
                        break
        except Exception:
            if not request_cancel.is_set():
                raise
        finally:
            self._unregister_stream(response_id)

        if tool_calls and not request_cancel.is_set():
            yield {
                "type": "tool_calls",
                "tool_calls": list(tool_calls.values()),
                "seconds": round(perf_counter() - started, 3),
            }

