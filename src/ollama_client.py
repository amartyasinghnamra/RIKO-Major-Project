
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class OllamaClient:
    def __init__(
        self,
        model="qwen3:4b-instruct",
        base_url="http://127.0.0.1:11434"
    ):
        self.model = model
        self.chat_url = f"{base_url.rstrip('/')}/api/chat"

    def stream_response(self, messages):
        """
        Send conversation messages to Ollama
        and yield generated text chunks.
        """

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }

        request = Request(
            self.chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urlopen(request, timeout=120) as response:
                for line in response:
                    if not line.strip():
                        continue

                    data = json.loads(line.decode("utf-8"))

                    chunk = data.get("message", {}).get(
                        "content", ""
                    )

                    if chunk:
                        yield chunk

                    if data.get("done", False):
                        break

        except HTTPError as error:
            raise RuntimeError(
                f"Ollama returned HTTP error {error.code}"
            ) from error

        except URLError as error:
            raise RuntimeError(
                "Could not connect to Ollama. "
                "Check that Ollama is running."
            ) from error
