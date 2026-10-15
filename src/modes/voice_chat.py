"""Shared RIKO voice pipeline used by the CLI and native desktop GUI."""

from __future__ import annotations

import re
from pathlib import Path
import sys
from threading import Event, Thread
from time import perf_counter
from typing import Callable

from src.debug_logger import log_event, log_exception

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(PROJECT_ROOT / "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prompt_manager import PromptManager
from settings_manager import SettingsManager
from ollama_client import OllamaClient
from conversation_manager import ConversationManager


class VoiceChatSession:
    """The original CLI voice loop, exposed as a UI-neutral shared session.

    Audio capture, VAD, Faster-Whisper, Ollama streaming, Kokoro streaming,
    and barge-in all stay in RIKO's existing pipeline modules. Hosts receive
    small lifecycle/text events and may request a clean stop.
    """

    def __init__(
        self,
        project_root: Path = PROJECT_ROOT,
        prompt_manager=None,
        settings_manager=None,
        ollama_client=None,
        conversation=None,
        tts_factory=None,
        voice_input_factory=None,
        barge_in_monitor_factory=None,
    ):
        self.project_root = Path(project_root)
        self.prompt_manager = prompt_manager or PromptManager(self.project_root)
        self.settings = settings_manager or SettingsManager(self.project_root)
        self.ollama_client = ollama_client or OllamaClient()
        self.conversation = conversation or ConversationManager(
            self.prompt_manager,
            self.ollama_client,
            mode="voice",
        )
        self.conversation.enable_voice_status = True

        # Factories are injectable for regression tests; production imports
        # and constructs the same audio components as the original CLI loop.
        self.tts_factory = tts_factory
        self.voice_input_factory = voice_input_factory
        self.barge_in_monitor_factory = barge_in_monitor_factory

        self.stop_event = Event()
        self._response_cancel_event = Event()
        self.tts = None
        self.voice_input = None
        self.barge_in_monitor = None
        self._monitor_stop = None
        self._emit_callback: Callable[[str, object], None] | None = None

    def _emit(self, event: str, payload=None) -> None:
        if self._emit_callback is not None:
            self._emit_callback(event, payload)

    def stop(self) -> None:
        """Stop listening/playback and ask the session loop to exit."""
        self.stop_event.set()
        if self._monitor_stop is not None:
            self._monitor_stop.set()
        if self.tts is not None:
            try:
                self.tts.stop()
            except Exception as error:
                log_exception("VOICE", "Could not stop Kokoro playback", error)

    def stop_response_generation(
        self,
        *,
        preserve_interruption_capture: bool = False,
    ) -> bool:
        """Stop this reply while keeping the voice conversation available."""
        self._response_cancel_event.set()
        stop = getattr(self.conversation, "stop_response_generation", None)
        stopped = bool(stop()) if callable(stop) else False
        if self.tts is not None:
            try:
                self.tts.stop()
            except Exception as error:
                log_exception("VOICE", "Could not stop Kokoro playback", error)
        if self._monitor_stop is not None and not preserve_interruption_capture:
            self._monitor_stop.set()
        self._emit(
            "response_cancelled",
            "Voice interruption detected; listening for you."
            if preserve_interruption_capture
            else "Response stopped. Listening for you.",
        )
        return stopped

    def _stop_generation_for_barge_in(self) -> None:
        self.stop_response_generation(preserve_interruption_capture=True)

    def update_runtime_preferences(self) -> None:
        """Apply saved speech preferences to the active TTS stream."""
        if self.tts is None:
            return
        settings = self.settings.get_tts_settings()
        self.tts.voice = self.settings.get_tts_voice()
        self.tts.speed = float(settings.get("speed", 1.0))
        self.tts.lang = settings.get("language", "en-us")

    def _load_factories(self):
        if self.tts_factory is None:
            from audio.kokoro.tts import KokoroTTS

            self.tts_factory = KokoroTTS
        if self.voice_input_factory is None:
            from audio.stt.streaming_voice_input import StreamingVoiceInput

            self.voice_input_factory = StreamingVoiceInput
        if self.barge_in_monitor_factory is None:
            from audio.stt.barge_in_monitor import BargeInMonitor

            self.barge_in_monitor_factory = BargeInMonitor

    def _initialize(self):
        self._load_factories()
        tts_settings = self.settings.get_tts_settings()
        self.tts = self.tts_factory(
            voice=self.settings.get_tts_voice(),
            speed=tts_settings.get("speed", 1.0),
            lang=tts_settings.get("language", "en-us"),
        )
        self.tts.load()

        self.voice_input = self.voice_input_factory(
            model_size="base",
            device="cpu",
            compute_type="int8",
            language_mode="auto",
            silence_duration=0.8,
            energy_threshold=0.001,
            update_interval=0.8,
            window_seconds=6.0,
        )
        self.barge_in_monitor = self.barge_in_monitor_factory(
            stt=self.voice_input.stt,
            tts=self.tts,
            microphone_device=self.voice_input.microphone_device,
            energy_threshold=0.025,
            confirmation_seconds=0.30,
            silence_duration=0.8,
            max_record_seconds=15.0,
            on_interruption=self._stop_generation_for_barge_in,
        )

    def _warm_up_model(self, warmup_done: Event, warmup_state: dict) -> None:
        try:
            started = perf_counter()
            self.ollama_client.warm_up(self.conversation.messages[0]["content"])
            warmup_state["seconds"] = perf_counter() - started
        except Exception as error:
            warmup_state["error"] = error
        finally:
            warmup_done.set()

    def _respond_to(self, user_message: str, riko_name: str) -> str | None:
        self._response_cancel_event = Event()
        begin_response = getattr(self.conversation, "begin_response", None)
        if callable(begin_response):
            begin_response()

        # Settings may be changed while the voice window is open. Rebuild the
        # system prompt between turns so the current reply remains consistent.
        self.conversation.messages[0]["content"] = self.prompt_manager.build_prompt(
            mode="voice"
        )
        self._emit("response_started", riko_name)
        started = perf_counter()
        first_token_seen = False

        def visible_text_stream():
            nonlocal first_token_seen
            stream = self.conversation.stream_response(user_message)
            try:
                for chunk in stream:
                    if self.stop_event.is_set() or self._response_cancel_event.is_set():
                        break
                    if (
                        isinstance(chunk, tuple)
                        and len(chunk) == 2
                        and chunk[0] == "__RIKO_STATUS__"
                    ):
                        self._emit("status", str(chunk[1]))
                        yield chunk
                        continue
                    if (
                        isinstance(chunk, tuple)
                        and len(chunk) == 2
                        and chunk[0] == "__RIKO_TOOL__"
                    ):
                        self._emit("tool_call", chunk[1])
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
                    if chunk:
                        self._emit("token", chunk)
                    yield chunk
            finally:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()

        monitor_stop = Event()
        self._monitor_stop = monitor_stop
        monitor_result = {"text": None}

        # A monitor is shared across turns; reset its prior interruption flag
        # before it starts watching this response.
        self.barge_in_monitor.interrupted.clear()

        def monitor_for_barge_in():
            try:
                monitor_result["text"] = self.barge_in_monitor.listen(monitor_stop)
            except Exception as error:
                log_exception("VOICE", "Barge-in monitor failed", error)

        monitor_thread = Thread(
            target=monitor_for_barge_in,
            name="riko-barge-in-monitor",
            daemon=True,
        )
        monitor_thread.start()

        try:
            self.tts.speak_stream(visible_text_stream())
            log_event(
                "VOICE",
                "Response and playback finished",
                seconds=round(perf_counter() - started, 3),
            )
        finally:
            if self.barge_in_monitor.interrupted.is_set() and not self.stop_event.is_set():
                # The monitor owns the microphone until it finishes capturing
                # the user's interruption.
                monitor_thread.join(timeout=25.0)
            else:
                monitor_stop.set()
                monitor_thread.join(timeout=2.0)

            if monitor_thread.is_alive():
                monitor_stop.set()
                monitor_thread.join(timeout=1.0)
            self._monitor_stop = None

        transcript = monitor_result.get("text")
        if transcript and transcript.strip() and not self.stop_event.is_set():
            transcript = transcript.strip()
            log_event(
                "VOICE",
                "Barge-in transcript ready",
                transcript_chars=len(transcript),
            )
            if is_stop_response_command(transcript):
                self._emit("interruption_command", transcript)
                log_event("VOICE", "Response stop command recognized")
                return None
            return transcript
        return None

    def run(self, on_event: Callable[[str, object], None] | None = None) -> None:
        """Run the CLI voice conversation until stopped; emit events to host."""
        self._emit_callback = on_event
        warmup_done = Event()
        warmup_state = {"error": None, "seconds": None}

        try:
            Thread(
                target=self._warm_up_model,
                args=(warmup_done, warmup_state),
                name="riko-ollama-warmup",
                daemon=True,
            ).start()

            self._initialize()
            self._emit("ready", None)

            riko_name = self.prompt_manager.get_persona().get("name") or "Riko"
            self._emit("greeting", riko_name)
            pending_user_message = None

            while not self.stop_event.is_set():
                if pending_user_message:
                    user_message = pending_user_message
                    pending_user_message = None
                else:
                    self._emit("listening", None)
                    try:
                        user_message = self.voice_input.listen_once(
                            stop_event=self.stop_event,
                        )
                    except KeyboardInterrupt:
                        raise
                    except Exception as error:
                        log_exception("VOICE", "Microphone/STT listen failed", error)
                        self._emit("listen_error", str(error))
                        self.stop_event.wait(0.5)
                        continue

                if self.stop_event.is_set():
                    break
                if not user_message or not user_message.strip():
                    continue

                user_message = user_message.strip()
                log_event(
                    "VOICE",
                    "Transcript ready; beginning response generation",
                    transcript_chars=len(user_message),
                )
                self._emit("transcript", user_message)

                while not warmup_done.wait(timeout=0.1):
                    if self.stop_event.is_set():
                        break
                if self.stop_event.is_set():
                    break

                if warmup_state["error"] is not None:
                    self._emit("warning", f"Ollama warm-up warning: {warmup_state['error']}")
                    warmup_state["error"] = None
                elif warmup_state["seconds"] is not None:
                    log_event(
                        "VOICE",
                        "Startup warm-up completed",
                        seconds=round(warmup_state["seconds"], 3),
                    )
                    warmup_state["seconds"] = None

                try:
                    pending_user_message = self._respond_to(user_message, riko_name)
                except Exception as error:
                    log_exception("VOICE", "Voice response failed", error)
                    self._emit("turn_error", str(error))
                finally:
                    self._emit("turn_done", None)

        except Exception as error:
            log_exception("VOICE", "Voice chat initialization failed", error)
            self._emit("error", str(error))
        finally:
            self.stop_event.set()
            if self.tts is not None:
                try:
                    self.tts.stop()
                except Exception as error:
                    log_exception("VOICE", "Could not stop Kokoro playback", error)
            self._emit("ended", None)

    def run_cli(self):
        """Run the terminal event renderer over this shared voice session."""
        try:
            self.run(_print_cli_event)
        except KeyboardInterrupt:
            self.stop()
            name = self.prompt_manager.get_persona().get("name") or "Riko"
            print(f"\n\n{name}: See you later!")


def _print_cli_event(event: str, payload) -> None:
    """Render shared session events in the original terminal experience."""
    if event == "ready":
        print("[RIKO] Microphone input is ready.")
        print("[RIKO] Barge-in is enabled; headphones are recommended to reduce speaker echo.")
    elif event == "greeting":
        print(f"\n{payload}: Hello! I'm here whenever you're ready.")
        print("[RIKO] Voice Chat active. Speak naturally.")
        print("[RIKO] Press Ctrl+C to end the conversation.\n")
    elif event == "listening":
        print("\n[RIKO] Listening continuously... Speak when ready.")
    elif event == "listen_error":
        print(f"\n[RIKO STT error] {payload}")
        print("[RIKO] Trying to listen again...\n")
    elif event == "transcript":
        print(f"\n[You said] {payload}")
    elif event == "response_started":
        print(f"\n{payload}: ", end="", flush=True)
    elif event == "token":
        print(payload, end="", flush=True)
    elif event == "status":
        print(f"\n[RIKO] {payload}", flush=True)
    elif event == "response_cancelled":
        print(f"\n[RIKO] {payload}", flush=True)
    elif event == "interruption_command":
        print(f"\n[You said] {payload}")
    elif event == "turn_done":
        print("\n")
    elif event == "turn_error":
        print(f"\n[RIKO voice error] {payload}")
    elif event == "warning":
        print(f"[RIKO] {payload}")
    elif event == "error":
        print(f"[RIKO] Could not start Voice Chat: {payload}")
    elif event == "ended":
        print("[RIKO] Voice chat ended.")


def is_stop_response_command(transcript: str) -> bool:
    """Recognize short, direct spoken commands that should not reach Ollama."""
    normalized = re.sub(r"[^a-z0-9']+", " ", transcript.casefold()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized in {
        "stop", "wait", "pause", "cancel", "hold on", "hold up",
        "that's enough", "that is enough", "be quiet", "riko stop",
        "riko wait", "please stop", "please wait", "please pause",
        "stop please", "wait please", "pause please", "cancel that",
        "stop that", "stop talking", "stop speaking", "hang on",
        "hang on a second", "hold up a second", "wait a sec",
        "wait a minute", "one second", "one moment",
        "stop now", "wait a second", "wait a moment", "hold on a second",
        "please wait a second", "please wait a moment",
    }:
        return True
    return bool(re.fullmatch(r"(please )?(stop|wait|pause|cancel)( now| there)?", normalized))


def main():
    return VoiceChatSession().run_cli()


if __name__ == "__main__":
    main()
