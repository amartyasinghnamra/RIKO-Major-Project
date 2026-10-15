
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


class TextChatSession:
    """Reusable text-chat pipeline shared by the CLI and desktop GUI."""

    def __init__(self, prompt_manager=None, ollama_client=None, conversation=None):
        self.prompt_manager = prompt_manager or PromptManager(PROJECT_ROOT)
        self.ollama_client = ollama_client or OllamaClient()
        self.conversation = conversation or ConversationManager(
            self.prompt_manager, self.ollama_client, mode="text"
        )
        self.conversation.enable_text_status = True

    def stream_response(self, user_message):
        """Yield the same conversation events consumed by the text CLI."""
        yield from self.conversation.stream_response(user_message)

    def stop_response_generation(self) -> bool:
        """Cancel the active model response without ending text chat."""
        stop = getattr(self.conversation, "stop_response_generation", None)
        return bool(stop()) if callable(stop) else False

    def run_cli(self):
        """Run the terminal UI over this session's shared text pipeline."""
        persona = self.prompt_manager.get_persona()
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
                for chunk in self.stream_response(user_message):
                    if (
                        isinstance(chunk, tuple)
                        and len(chunk) == 2
                        and chunk[0] == "__RIKO_STATUS__"
                    ):
                        print(f"\n[RIKO] {chunk[1]}", flush=True)
                    else:
                        print(chunk, end="", flush=True)
                print("\n")
            except Exception as error:
                print(f"\n[RIKO error] {error}\n")


def main():
    return TextChatSession().run_cli()


if __name__ == "__main__":
    main()
