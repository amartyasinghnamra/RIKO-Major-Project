
"""RIKO voice-only chat mode."""
from pathlib import Path
import sys
from threading import Event, Thread
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(PROJECT_ROOT / "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prompt_manager import PromptManager
from ollama_client import OllamaClient
from conversation_manager import ConversationManager
from audio.kokoro.tts import KokoroTTS


def main():
    prompt_manager = PromptManager(PROJECT_ROOT)
    ollama_client = OllamaClient()

    conversation = ConversationManager(
        prompt_manager,
        ollama_client,
        mode="voice",

    )

    persona = prompt_manager.get_persona()
    riko_name = persona.get("name") or "Riko"

    tts = KokoroTTS()

    warmup_done = Event()
    warmup_state = {"error": None, "seconds": None}
    system_prompt = conversation.messages[0]["content"]

    def warm_up_model():
        try:
            started = perf_counter()
            ollama_client.warm_up(system_prompt)
            warmup_state["seconds"] = perf_counter() - started
        except Exception as error:
            warmup_state["error"] = error
        finally:
            warmup_done.set()

    Thread(
        target=warm_up_model,
        name="riko-ollama-warmup",
        daemon=True,
    ).start()

    try:
        tts.load()
    except Exception as error:
        print(f"[RIKO] Could not initialize Kokoro: {error}")
        return

    print(f"{riko_name}: Hello! I'm here whenever you're ready.")
    print("[RIKO] Voice Chat mode. Type 'exit' to leave.\n")

    try:
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

            warmup_done.wait()

            if warmup_state["error"] is not None:
                print(f"[RIKO warm-up warning] {warmup_state['error']}")
                warmup_state["error"] = None
            elif warmup_state["seconds"] is not None:
                print(
                    "[Latency] Startup warm-up: "
                    f"{warmup_state['seconds']:.2f} s"
                )
                warmup_state["seconds"] = None

            print(f"\n{riko_name}: ", end="", flush=True)
            started = perf_counter()

            def visible_text_stream():
                for chunk in conversation.stream_response(user_message):
                    print(chunk, end="", flush=True)
                    yield chunk

            try:
                tts.speak_stream(visible_text_stream())
                elapsed = perf_counter() - started
                print(
                    "\n[Latency] Response and playback finished: "
                    f"{elapsed:.2f} s\n"
                )
            except Exception as error:
                print(f"\n[RIKO voice error] {error}\n")
    finally:
        tts.stop()


if __name__ == "__main__":
    main()
