import json
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

    def _post_chat(self, messages, *, stream, options=None):
        """Send a chat request to Ollama with consistent model residency."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
        }

        if options is not None:
            payload["options"] = options

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

    def warm_up(self, system_prompt):
        """Load the model and evaluate RIKO's actual system prompt."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Reply with exactly: Ready."},
        ]

        started = perf_counter()
        with self._post_chat(
            messages,
            stream=False,
            options={"num_predict": 1},
        ) as response:
            response.read()

        return perf_counter() - started

    def stream_response(self, messages, *, on_first_token=None, on_metrics=None):
        """
        Stream generated text. Optional callbacks report time-to-first-token
        and total request duration without changing the yielded text.
        """
        started = perf_counter()
        first_token_seconds = None

        with self._post_chat(messages, stream=True) as response:
            for line in response:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as error:
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
                    total_seconds = perf_counter() - started
                    if on_metrics is not None:
                        on_metrics({
                            "time_to_first_token_seconds": first_token_seconds,
                            "total_seconds": total_seconds,
                            "prompt_eval_count": data.get("prompt_eval_count"),
                            "prompt_eval_duration_ns": data.get("prompt_eval_duration"),
                            "eval_count": data.get("eval_count"),
                            "eval_duration_ns": data.get("eval_duration"),
                            "load_duration_ns": data.get("load_duration"),
                            "total_duration_ns": data.get("total_duration"),
                        })
                    break
