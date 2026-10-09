
"""RIKO text-only chat mode. No audio dependencies."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(PROJECT_ROOT / "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prompt_manager import PromptManager
from ollama_client import OllamaClient
from conversation_manager import ConversationManager


def main():
    prompt_manager = PromptManager(PROJECT_ROOT)
    ollama_client = OllamaClient()

    conversation = ConversationManager(
        prompt_manager,
        ollama_client,
    )

    persona = prompt_manager.get_persona()
    riko_name = persona.get("name") or "Riko"

    print(f"{riko_name}: Hello! I'm here whenever you're ready.")
    print("[RIKO] Text Chat mode. Type 'exit' to leave.\n")

    while True:
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{riko_name}: See you later!")
            break

        if user_message.lower() == "exit":
            print(f"{riko_name}: See you later!")
            break

        if not user_message:
            continue

        print(f"\n{riko_name}: ", end="", flush=True)

        try:
            for chunk in conversation.stream_response(user_message):
                print(chunk, end="", flush=True)
            print("\n")
        except Exception as error:
            print(f"\n[RIKO error] {error}\n")


if __name__ == "__main__":
    main()
