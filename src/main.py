
from pathlib import Path

from prompt_manager import PromptManager
from ollama_client import OllamaClient
from conversation_manager import ConversationManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    prompt_manager = PromptManager(PROJECT_ROOT)
    ollama_client = OllamaClient()

    conversation = ConversationManager(
        prompt_manager,
        ollama_client
    )

    print("Riko: Hey Amartya! I'm here. Talk to me.")
    print("Type 'exit' to end the conversation.\n")

    while True:
        user_message = input("You: ").strip()

        if user_message.lower() == "exit":
            print("Riko: Okay, see you later!")
            break

        if not user_message:
            continue

        print("\nRiko: ", end="", flush=True)

        try:
            for chunk in conversation.stream_response(
                user_message
            ):
                print(chunk, end="", flush=True)

            print("\n")

        except (RuntimeError, TimeoutError) as error:
            print(f"\n[RIKO error] {error}\n")


if __name__ == "__main__":
    main()
