
from ollama_client import OllamaClient


def main():
    client = OllamaClient()

    messages = [
        {
            "role": "user",
            "content": (
                "Introduce yourself as Riko in two short sentences."
            )
        }
    ]

    print("RIKO: ", end="", flush=True)

    for chunk in client.stream_response(messages):
        print(chunk, end="", flush=True)

    print("\n\nOllamaClient test completed.")


if __name__ == "__main__":
    main()
