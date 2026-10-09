from pathlib import Path

from prompt_manager import PromptManager
from ollama_client import OllamaClient
from conversation_manager import ConversationManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    prompt_manager = PromptManager(PROJECT_ROOT)
    ollama_client = OllamaClient()

    persona = prompt_manager.get_persona()
    assistant_name = persona.get("name", "Riko")
    greeting = persona.get("greeting", "Hello! I'm here.")

    conversation = ConversationManager(
        prompt_manager,
        ollama_client
    )

    print(f"{assistant_name}: {greeting}")
    print("Type 'exit' to end the conversation.\n")

    while True:
        user_message = input("You: ").strip()

        if user_message.lower() == "exit":
            print(f"{assistant_name}: Okay, see you later!")
            break

        if not user_message:
            continue

        print(f"\n{assistant_name}: ", end="", flush=True)

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
