
"""RIKO entry point: choose Text Chat or Voice Chat."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SRC_DIR = str(PROJECT_ROOT / "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prompt_manager import PromptManager
from settings_manager import SettingsManager


def create_chat_session(mode, **dependencies):
    """Create a shared mode session for either CLI or GUI hosts."""
    if mode == "text":
        from modes.text_chat import TextChatSession

        return TextChatSession(**dependencies)
    if mode == "voice":
        # Keep audio dependencies lazy until a voice session is requested.
        from modes.voice_chat import VoiceChatSession

        dependencies.setdefault("project_root", PROJECT_ROOT)
        return VoiceChatSession(**dependencies)
    raise ValueError("mode must be 'text' or 'voice'")


def run_text_chat(session=None, message=None):
    """Run the CLI text UI, or stream one turn for a GUI host."""
    if session is None:
        session = create_chat_session("text")
    if message is not None:
        return session.stream_response(message)
    return session.run_cli()


def run_voice_chat(session=None, on_event=None):
    """Run the CLI voice UI or a host-provided event consumer over a session."""
    if session is None:
        session = create_chat_session("voice")
    if on_event is None:
        return session.run_cli()
    return session.run(on_event)


def settings_menu():
    """Interactive local persona and Kokoro settings."""
    settings = SettingsManager(PROJECT_ROOT)
    prompts = PromptManager(PROJECT_ROOT)

    while True:
        current_voice = settings.get_tts_voice()
        current_persona = settings.get_persona()
        current_profile = settings.get_profile()
        tts = settings.get_tts_settings()

        print("\\n========== RIKO SETTINGS ==========")
        print(f"Persona: {current_persona}")
        print(f"Profile context: {current_profile}")
        print(f"Kokoro voice: {current_voice}")
        print(f"Speech speed: {tts.get('speed', 1.0)}")
        print("1. Select persona")
        print("2. Select Kokoro voice")
        print("3. Set speech speed")
        print("4. Select profile context")
        print("0. Back")

        choice = input("\\nChoose option: ").strip()

        if choice == "0":
            return

        elif choice == "1":
            personas = prompts.list_personas()
            if not personas:
                print("No valid personas were found.")
                continue

            print("\\nAvailable personas:")
            for index, persona in enumerate(personas, start=1):
                print(
                    f"{index}. {persona['name']} "
                    f"({persona['id']}) — {persona['description']}"
                )

            selected = input("Enter persona number (or 0 to cancel): ").strip()
            if selected == "0":
                continue

            try:
                index = int(selected) - 1
                if not 0 <= index < len(personas):
                    raise ValueError
                prompts.select_persona(personas[index]["id"])
                print(f"Selected persona: {personas[index]['id']}")
            except ValueError:
                print("Invalid persona selection.")

        elif choice == "2":
            try:
                from audio.kokoro.voice_registry import KokoroVoiceRegistry

                registry = KokoroVoiceRegistry()
                voices = registry.list_voices()
            except Exception as error:
                print(f"Could not load Kokoro voices: {error}")
                continue

            if not voices:
                print("No Kokoro voices were found.")
                continue

            print("\\nAvailable Kokoro voices:")
            for index, voice in enumerate(voices, start=1):
                marker = " (current)" if voice == current_voice else ""
                print(f"{index}. {voice}{marker}")

            selected = input("Enter voice number (or 0 to cancel): ").strip()
            if selected == "0":
                continue

            try:
                index = int(selected) - 1
                if not 0 <= index < len(voices):
                    raise ValueError
                settings.set_tts_voice(voices[index], voices)
                print(f"Selected Kokoro voice: {voices[index]}")
            except ValueError as error:
                print(f"Invalid voice selection: {error}")

        elif choice == "3":
            selected = input("Speech speed (0.25–4.0, or 0 to cancel): ").strip()
            if selected == "0":
                continue

            try:
                settings.set_tts_speed(float(selected))
                print(f"Speech speed saved: {settings.get_tts_settings()['speed']}")
            except ValueError as error:
                print(f"Invalid speed: {error}")

        elif choice == "4":
            profiles = prompts.list_profiles()
            print("\nAvailable profiles:")
            for index, profile in enumerate(profiles, start=1):
                marker = " (current)" if profile["id"] == current_profile else ""
                print(f"{index}. {profile['name']} ({profile['id']}){marker}")
                if profile["description"]:
                    print(f"   {profile['description']}")

            selected = input("Enter profile number (or 0 to cancel): ").strip()
            if selected == "0":
                continue
            try:
                index = int(selected) - 1
                if not 0 <= index < len(profiles):
                    raise ValueError
                prompts.select_profile(profiles[index]["id"])
                print(f"Selected profile context: {profiles[index]['id']}")
            except ValueError:
                print("Invalid profile selection.")

        else:
            print("Invalid choice.")


def main():
    print("\n========== RIKO ==========")
    print("1. Text Chat")
    print("2. Voice Chat")
    print("3. Settings & Selectors")
    print("0. Exit")

    choice = input("\nChoose mode: ").strip()

    if choice == "1":
        run_text_chat()
    elif choice == "2":
        run_voice_chat()
    elif choice == "3":
        settings_menu()
    elif choice == "0":
        print("RIKO closed.")
    else:
        print("Invalid choice. Run RIKO again and choose 0, 1, 2, or 3.")


if __name__ == "__main__":
    main()
