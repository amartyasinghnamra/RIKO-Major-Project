"""CLI and GUI hosts consume the same text and voice session pipelines."""

from __future__ import annotations

import queue
from threading import Event

from GUI import app as gui_app
from modes.text_chat import TextChatSession
from modes.voice_chat import VoiceChatSession, is_stop_response_command
from audio.stt import streaming_voice_input


class FakePrompts:
    def get_persona(self):
        return {"name": "Riko"}

    def build_prompt(self, mode="text"):
        return f"system prompt for {mode}"


class FakeSettings:
    def get_tts_settings(self):
        return {"speed": 1.1, "language": "en-us"}

    def get_tts_voice(self):
        return "af_heart"


class FakeConversation:
    def __init__(self):
        self.messages = [{"role": "system", "content": "voice prompt"}]
        self.received = []
        self.enable_voice_status = False
        self.enable_text_status = False

    def stream_response(self, message):
        self.received.append(message)
        yield f"Reply to {message}."


def test_text_session_wraps_the_cli_conversation_stream():
    conversation = FakeConversation()
    session = TextChatSession(
        prompt_manager=FakePrompts(),
        ollama_client=object(),
        conversation=conversation,
    )

    assert session.conversation is conversation
    assert conversation.enable_text_status is True
    assert list(session.stream_response("hello")) == ["Reply to hello."]
    assert conversation.received == ["hello"]


def test_voice_session_runs_original_stt_streaming_tts_and_barge_in_path():
    conversation = FakeConversation()
    emitted = []
    captured = {}

    class FakeClient:
        def warm_up(self, _prompt):
            captured["warm_up"] = True

    class FakeTTS:
        def __init__(self, **kwargs):
            captured["tts_settings"] = kwargs
            self.responses = []
            captured["tts"] = self

        def load(self):
            captured["tts_loaded"] = True

        def speak_stream(self, chunks):
            self.responses.append("".join(chunk for chunk in chunks if isinstance(chunk, str)))

        def stop(self):
            captured["tts_stopped"] = True

    session_ref = {}

    class FakeStreamingVoiceInput:
        def __init__(self, **kwargs):
            captured["stt_settings"] = kwargs
            self.stt = object()
            self.microphone_device = "default-mic"
            self.listened = 0

        def listen_once(self, stop_event):
            assert stop_event is session_ref["session"].stop_event
            self.listened += 1
            if self.listened == 1:
                return "first question"
            stop_event.set()
            return ""

    class FakeBargeInMonitor:
        def __init__(self, **kwargs):
            captured["barge_settings"] = kwargs
            self.interrupted = Event()
            self.turns = 0

        def listen(self, _stop_event):
            self.turns += 1
            if self.turns == 1:
                self.interrupted.set()
                return "barge-in follow-up"
            return None

    session = VoiceChatSession(
        prompt_manager=FakePrompts(),
        settings_manager=FakeSettings(),
        ollama_client=FakeClient(),
        conversation=conversation,
        tts_factory=FakeTTS,
        voice_input_factory=FakeStreamingVoiceInput,
        barge_in_monitor_factory=FakeBargeInMonitor,
    )
    session_ref["session"] = session

    session.run(lambda event, payload: emitted.append((event, payload)))

    assert conversation.enable_voice_status is True
    assert conversation.received == ["first question", "barge-in follow-up"]
    assert [item for item in emitted if item[0] == "transcript"] == [
        ("transcript", "first question"),
        ("transcript", "barge-in follow-up"),
    ]
    assert [payload for event, payload in emitted if event == "token"] == [
        "Reply to first question.",
        "Reply to barge-in follow-up.",
    ]
    assert captured["tts_settings"] == {
        "voice": "af_heart", "speed": 1.1, "lang": "en-us"
    }
    assert captured["stt_settings"] == {
        "model_size": "base",
        "device": "cpu",
        "compute_type": "int8",
        "language_mode": "auto",
        "silence_duration": 0.8,
        "energy_threshold": 0.001,
        "update_interval": 0.8,
        "window_seconds": 6.0,
    }
    assert captured["barge_settings"]["stt"] is session.voice_input.stt
    assert captured["barge_settings"]["microphone_device"] == "default-mic"
    assert callable(captured["barge_settings"]["on_interruption"])
    assert captured["tts_loaded"] is True
    assert captured["tts_stopped"] is True
    assert captured["tts"].responses == [
        "Reply to first question.",
        "Reply to barge-in follow-up.",
    ]
    assert emitted[-1] == ("ended", None)


def test_gui_imports_and_starts_the_shared_cli_sessions():
    import inspect

    source = inspect.getsource(gui_app)

    assert "create_chat_session" in source
    assert "run_text_chat" in source
    assert "run_voice_chat" in source
    assert "TextChatSession" not in source
    assert "VoiceChatSession" not in source
    assert "StreamingVoiceInput" not in source
    assert "FasterWhisperSTT" not in source
    assert "MicrophoneCapture" not in source


def test_shared_streaming_input_can_be_stopped_by_a_desktop_host(monkeypatch):
    stopped = Event()
    stopped.set()
    lifecycle = []

    class FakeMicrophone:
        def __init__(self, **kwargs):
            lifecycle.append(("create", kwargs))

        def __enter__(self):
            lifecycle.append(("start", None))
            return self

        def __exit__(self, *_args):
            lifecycle.append(("stop", None))

    monkeypatch.setattr(
        streaming_voice_input,
        "MicrophoneCapture",
        FakeMicrophone,
    )
    voice_input = streaming_voice_input.StreamingVoiceInput.__new__(
        streaming_voice_input.StreamingVoiceInput
    )
    voice_input.silence_duration = 0.8
    voice_input.energy_threshold = 0.001
    voice_input.speech_timeout = 10.0
    voice_input.max_record_seconds = 20.0
    voice_input.update_interval = 0.8
    voice_input.window_seconds = 6.0
    voice_input.microphone_device = "mock-mic"

    assert voice_input.listen_once(stop_event=stopped) == ""
    assert [item[0] for item in lifecycle] == ["create", "start", "stop"]


def test_voice_stop_commands_are_consumed_as_controls():
    for phrase in (
        "stop",
        "Wait!",
        "Riko, stop.",
        "please wait a second",
        "hold on",
        "that's enough",
    ):
        assert is_stop_response_command(phrase)

    assert not is_stop_response_command("Wait, can you explain the next part?")
    assert not is_stop_response_command("Please stop using that example.")


def test_voice_stop_cancels_reply_but_keeps_listening_session_alive():
    stopped = []

    class CancellableConversation:
        def stop_response_generation(self):
            stopped.append("model")
            return True

    class FakeTTS:
        def stop(self):
            stopped.append("tts")

    session = VoiceChatSession.__new__(VoiceChatSession)
    session.conversation = CancellableConversation()
    session.tts = FakeTTS()
    session.stop_event = Event()
    session._response_cancel_event = Event()
    session._monitor_stop = Event()
    session._emit_callback = None

    assert session.stop_response_generation() is True
    assert stopped == ["model", "tts"]
    assert session._response_cancel_event.is_set()
    assert session._monitor_stop.is_set()
    assert not session.stop_event.is_set()


def test_saved_speech_preferences_update_the_active_voice_pipeline():
    session = VoiceChatSession.__new__(VoiceChatSession)
    session.settings = FakeSettings()
    session.tts = type(
        "FakeTTSPreferences",
        (),
        {"voice": "af_sarah", "speed": 1.0, "lang": "en-us"},
    )()

    session.update_runtime_preferences()

    assert session.tts.voice == "af_heart"
    assert session.tts.speed == 1.1
    assert session.tts.lang == "en-us"
