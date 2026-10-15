"""RIKO voice-only companion chat."""

from pathlib import Path
import sys
from threading import Event, Thread
from time import perf_counter

from src.debug_logger import log_event, log_exception

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(PROJECT_ROOT / "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prompt_manager import PromptManager
from settings_manager import SettingsManager
from ollama_client import OllamaClient
from conversation_manager import ConversationManager
from audio.kokoro.tts import KokoroTTS
from audio.stt.streaming_voice_input import StreamingVoiceInput
from audio.stt.barge_in_monitor import BargeInMonitor


def main():
    prompt_manager = PromptManager(PROJECT_ROOT)
    ollama_client = OllamaClient()

    conversation = ConversationManager(
        prompt_manager,
        ollama_client,
        mode="voice",
    )
    conversation.enable_voice_status = True

    persona = prompt_manager.get_persona()
    riko_name = persona.get("name") or "Riko"

    settings = SettingsManager(PROJECT_ROOT)
    tts_settings = settings.get_tts_settings()

    tts = KokoroTTS(
        voice=settings.get_tts_voice(),
        speed=tts_settings.get("speed", 1.0),
        lang=tts_settings.get("language", "en-us"),
    )
    voice_input = None

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

    try:
        voice_input = StreamingVoiceInput(
            model_size="base",
            device="cpu",
            compute_type="int8",
            language_mode="auto",
            silence_duration=0.8,
            energy_threshold=0.001,
            update_interval=0.8,
            window_seconds=6.0,
        )
        barge_in_monitor = BargeInMonitor(
            stt=voice_input.stt,
            tts=tts,
            microphone_device=voice_input.microphone_device,
            energy_threshold=0.025,
            confirmation_seconds=0.30,
            silence_duration=0.8,
            max_record_seconds=15.0,
        )
        print("[RIKO] Microphone input is ready.")
        print("[RIKO] Barge-in is enabled; headphones are recommended to reduce speaker echo.")
    except Exception as error:
        print(f"[RIKO] Could not initialize microphone STT: {error}")
        tts.stop()
        return

    print(f"\n{riko_name}: Hello! I'm here whenever you're ready.")
    print("[RIKO] Voice Chat active. Speak naturally.")
    print("[RIKO] Press Ctrl+C to end the conversation.\n")

    pending_user_message = None

    try:
        while True:
            try:
                if pending_user_message:
                    user_message = pending_user_message
                    pending_user_message = None
                    print(f"\n[You said - barge-in] {user_message}")
                else:
                    user_message = voice_input.listen_once()
            except KeyboardInterrupt:
                print(f"\n\n{riko_name}: See you later!")
                break
            except Exception as error:
                print(f"\n[RIKO STT error] {error}")
                print("[RIKO] Trying to listen again...\n")
                continue

            if not user_message or not user_message.strip():
                continue

            log_event(
                "VOICE",
                "Transcript ready; beginning response generation",
                transcript_chars=len(user_message),
            )

            warmup_done.wait()

            if warmup_state["error"] is not None:
                print(f"[RIKO warm-up warning] {warmup_state['error']}")
                warmup_state["error"] = None
            elif warmup_state["seconds"] is not None:
                log_event(
                    "VOICE",
                    "Startup warm-up completed",
                    seconds=round(warmup_state["seconds"], 3),
                )
                warmup_state["seconds"] = None

            print(f"\n{riko_name}: ", end="", flush=True)
            started = perf_counter()
            first_token_seen = False

            def visible_text_stream():
                nonlocal first_token_seen
                for chunk in conversation.stream_response(user_message):
                    if (
                        isinstance(chunk, tuple)
                        and len(chunk) == 2
                        and chunk[0] == "__RIKO_STATUS__"
                    ):
                        yield chunk
                        continue

                    if not isinstance(chunk, str):
                        continue

                    if chunk and not first_token_seen:
                        first_token_seen = True
                        log_event(
                            "VOICE",
                            "First LLM text chunk received",
                            seconds_since_response_start=round(
                                perf_counter() - started, 3
                            ),
                            chunk_chars=len(chunk),
                        )
                    print(chunk, end="", flush=True)
                    yield chunk

            monitor_stop = Event()
            monitor_result = {"text": None}

            def monitor_for_barge_in():
                try:
                    monitor_result["text"] = barge_in_monitor.listen(monitor_stop)
                except Exception as error:
                    log_exception("VOICE", "Barge-in monitor failed", error)

            monitor_thread = Thread(
                target=monitor_for_barge_in,
                name="riko-barge-in-monitor",
                daemon=True,
            )
            monitor_thread.start()

            try:
                tts.speak_stream(visible_text_stream())
                elapsed = perf_counter() - started
                log_event(
                    "VOICE",
                    "Response and playback finished",
                    seconds=round(elapsed, 3),
                )
            except KeyboardInterrupt:
                print("\n[RIKO] Conversation interrupted.")
                break
            except Exception as error:
                log_exception("VOICE", "Voice response failed", error)
            finally:
                if barge_in_monitor.interrupted.is_set():
                    # Once interrupted, let the monitor finish collecting the utterance.
                    monitor_thread.join(timeout=25.0)
                else:
                    monitor_stop.set()
                    monitor_thread.join(timeout=2.0)

                if monitor_thread.is_alive():
                    monitor_stop.set()
                    monitor_thread.join(timeout=1.0)

                transcript = monitor_result.get("text")
                if transcript and transcript.strip():
                    pending_user_message = transcript.strip()
                    log_event(
                        "VOICE",
                        "Barge-in transcript ready",
                        transcript_chars=len(pending_user_message),
                    )

    finally:
        tts.stop()


if __name__ == "__main__":
    main()