"""Regression coverage for the native GUI send and mode-routing paths."""

from __future__ import annotations

import queue
from unittest.mock import Mock

from GUI import app as gui_app


def test_zoom_targets_are_clamped_and_have_normal_steps():
    assert gui_app._clamp_zoom(0.1) == 0.8
    assert gui_app._clamp_zoom(1.25) == 1.25
    assert gui_app._clamp_zoom(2.0) == 1.6


def test_zoom_shortcuts_cover_keyboard_and_mousewheel():
    class Root:
        bindings = {}

        def bind_all(self, sequence, callback):
            self.bindings[sequence] = callback

    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.root = Root()
    desktop._bind_zoom_shortcuts()

    assert "<Control-plus>" in desktop.root.bindings
    assert "<Control-equal>" in desktop.root.bindings
    assert "<Control-minus>" in desktop.root.bindings
    assert "<Control-0>" in desktop.root.bindings
    assert "<Control-MouseWheel>" in desktop.root.bindings


def test_markdown_segments_render_common_reply_formatting():
    segments = gui_app._markdown_segments(
        "# A heading\n**important** and *gentle* with `code`\n- one item\n"
    )

    assert ("A heading", ("heading1",)) in segments
    assert ("important", ("bold",)) in segments
    assert ("gentle", ("italic",)) in segments
    assert ("code", ("inline_code",)) in segments
    assert ("• ", ("list",)) in segments
    assert all("**" not in text and "`" not in text for text, _tags in segments)


def test_reply_content_prefers_markdown_renderer_when_available():
    class MarkdownControl:
        rendered = None

        def set_markdown(self, text):
            self.rendered = text

    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.active_reply_label = MarkdownControl()

    desktop._set_reply_content("**formatted** reply")

    assert desktop.active_reply_label.rendered == "**formatted** reply"


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Control:
    def __init__(self):
        self.config = {}
        self.calls = []

    def configure(self, **kwargs):
        self.config.update(kwargs)

    def grid(self, **kwargs):
        self.calls.append(("grid", kwargs))

    def grid_remove(self):
        self.calls.append(("grid_remove", {}))

    def pack(self, **kwargs):
        self.calls.append(("pack", kwargs))

    def pack_forget(self):
        self.calls.append(("pack_forget", {}))

    def focus_set(self):
        self.calls.append(("focus_set", {}))


class TextInput(Control):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def get(self, *_args):
        return self.value

    def delete(self, *_args):
        self.value = ""


def test_text_send_routes_the_composed_message_to_text_mode():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.mode_var = Value("text")
    desktop.busy = False
    desktop.voice_session_active = False
    desktop.voice_stopping = False
    desktop.voice_restart_after_stop = False
    desktop.input = TextInput("Explain this clearly")
    desktop._start_message = Mock()

    desktop.send_message()

    desktop._start_message.assert_called_once_with("Explain this clearly", "text")


def test_voice_mode_hides_chat_composer_and_send_button():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.mode_var = Value("text")
    desktop.busy = False
    desktop.voice_session_active = False
    desktop.voice_stopping = False
    desktop.voice_restart_after_stop = False
    desktop.mode_buttons = {"text": Control(), "voice": Control()}
    desktop.mode_hint = Control()
    desktop.keyboard_hint = Control()
    desktop.text_panel = Control()
    desktop.voice_panel = Control()
    desktop.voice_status_label = Control()
    desktop.send_button = Control()
    desktop.start_voice_session = Mock()

    desktop.set_mode("voice")

    assert desktop.mode_var.get() == "voice"
    assert ("grid_remove", {}) in desktop.text_panel.calls
    assert any(call[0] == "grid" for call in desktop.voice_panel.calls)
    assert ("pack_forget", {}) in desktop.send_button.calls
    desktop.start_voice_session.assert_called_once_with()


def test_voice_mode_cannot_send_typed_chat_text():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.mode_var = Value("voice")
    desktop.busy = False
    desktop.voice_session_active = False
    desktop._start_message = Mock()

    desktop.send_message()

    desktop._start_message.assert_not_called()


def test_voice_transcription_is_shown_in_the_shared_conversation():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop._add_message = Mock()
    desktop.welcome_frame = None
    desktop.current_reply = ""
    desktop.status_var = Value("")

    desktop.handle_voice_transcription("  turn left at the next street  ")

    desktop._add_message.assert_any_call("you", "turn left at the next street")
    desktop._add_message.assert_any_call("riko", "…")
    assert desktop.status_var.get() == "RIKO is replying aloud…"


def test_shared_voice_pipeline_events_update_the_visible_reply():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop._add_message = Mock(return_value=Control())
    desktop.welcome_frame = None
    desktop.current_reply = ""
    desktop.active_reply_label = Control()
    desktop.status_var = Value("")
    desktop.busy = False
    desktop.voice_status_label = Control()
    desktop.handle_voice_transcription("open the settings")

    desktop._handle_voice_pipeline_event("response_started", "Riko")
    desktop._handle_voice_pipeline_event("token", "Here are")
    desktop._handle_voice_pipeline_event("token", " the settings.")

    assert desktop.busy is True
    assert desktop.current_reply == "Here are the settings."
    assert desktop.active_reply_label.config["text"] == "Here are the settings."
    desktop._handle_voice_pipeline_event("turn_done", None)
    assert desktop.busy is False


def test_shared_voice_transcript_does_not_send_through_text_composer():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.events = queue.Queue()
    desktop.events.put(("voice_pipeline", ("transcript", "open the settings")))
    desktop.status_var = Value("")
    desktop.root = type("Root", (), {"after": lambda *_args: None})()
    desktop._add_message = Mock(return_value=Control())
    desktop.welcome_frame = None
    desktop.current_reply = ""
    desktop.active_reply_label = None
    desktop.busy = False

    desktop._drain_events()

    desktop._add_message.assert_any_call("you", "open the settings")
    assert desktop.busy is False


def test_desktop_text_stream_uses_the_shared_cli_text_session(monkeypatch):
    class FakeConversation:
        def __init__(self):
            self.messages = [{"role": "system", "content": "old"}]
            self.enable_text_status = False
            self.enable_voice_status = False
            self.received = []

        def stream_response(self, message):
            self.received.append(message)
            yield "shared text reply"

    class FakePrompts:
        def build_prompt(self, mode="text"):
            return f"prompt:{mode}"

    class FakeTextSession:
        def __init__(self, prompt_manager, conversation):
            self.conversation = conversation or FakeConversation()
            self.prompt_manager = prompt_manager

        def stream_response(self, message):
            yield from self.conversation.stream_response(message)

    def create_session(mode, **kwargs):
        assert mode == "text"
        return FakeTextSession(
            prompt_manager=kwargs["prompt_manager"],
            conversation=kwargs.get("conversation"),
        )

    monkeypatch.setattr(gui_app, "create_chat_session", create_session)
    monkeypatch.setattr(
        gui_app,
        "run_text_chat",
        lambda session, message: session.stream_response(message),
    )
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.text_session = None
    desktop.conversation = None
    desktop.prompts = FakePrompts()
    desktop.events = queue.Queue()

    conversation = desktop._conversation_for("text")
    assert list(desktop._response_tokens(conversation, "hello")) == [
        "shared text reply"
    ]
    assert desktop.text_session.conversation is conversation
    assert conversation.messages[0]["content"] == "prompt:text"
    assert conversation.received == ["hello"]
    assert desktop.events.get_nowait() == ("token", "shared text reply")


def test_selecting_voice_starts_the_shared_cli_voice_session_automatically(monkeypatch):
    created = {}

    class FakeSession:
        def __init__(self, **kwargs):
            created["kwargs"] = kwargs
            self.conversation = object()

        def stop(self):
            created["stopped"] = True

    class FakeThread:
        def __init__(self, **kwargs):
            created["thread"] = kwargs

        def start(self):
            created["started"] = True

    def create_session(mode, **kwargs):
        assert mode == "voice"
        created["mode_and_kwargs"] = (mode, kwargs)
        return FakeSession(**kwargs)

    monkeypatch.setattr(gui_app, "create_chat_session", create_session)
    monkeypatch.setattr(gui_app.threading, "Thread", FakeThread)

    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.busy = False
    desktop.voice_session_active = False
    desktop.voice_stopping = False
    desktop.voice_restart_after_stop = False
    desktop.mode_var = Value("text")
    desktop.voice_session = None
    desktop.prompts = object()
    desktop.settings = object()
    desktop.mode_buttons = {"text": Control(), "voice": Control()}
    desktop.mode_hint = Control()
    desktop.keyboard_hint = Control()
    desktop.text_panel = Control()
    desktop.voice_panel = Control()
    desktop.voice_status_label = Control()
    desktop.send_button = Control()
    desktop.status_var = Value("")

    desktop.set_mode("voice")

    assert created["mode_and_kwargs"][0] == "voice"
    assert created["kwargs"]["prompt_manager"] is desktop.prompts
    assert created["kwargs"]["settings_manager"] is desktop.settings
    assert desktop.conversation is desktop.voice_session.conversation
    assert created["started"] is True
    assert desktop.voice_session_active is True
    assert desktop.mode_var.get() == "voice"
    assert not hasattr(desktop, "record_button")


def test_selecting_chat_requests_voice_shutdown_without_a_record_control():
    stopped = []

    class FakeSession:
        def stop(self):
            stopped.append(True)

    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.mode_var = Value("voice")
    desktop.busy = False
    desktop.voice_session_active = True
    desktop.voice_stopping = False
    desktop.voice_restart_after_stop = False
    desktop.voice_session = FakeSession()
    desktop.mode_buttons = {"text": Control(), "voice": Control()}
    desktop.mode_hint = Control()
    desktop.keyboard_hint = Control()
    desktop.text_panel = Control()
    desktop.voice_panel = Control()
    desktop.voice_status_label = Control()
    desktop.send_button = Control()
    desktop.status_var = Value("")

    desktop.set_mode("text")

    assert desktop.mode_var.get() == "text"
    assert stopped == [True]
    assert desktop.voice_session_active is True  # Remains guarded until ended event.
    assert desktop.voice_stopping is True
    assert desktop.voice_status_label.config["text"] == "Stopping voice chat…"
    assert not hasattr(desktop, "record_button")


def test_streamed_ollama_tokens_update_the_visible_reply_label():
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.events = queue.Queue()
    desktop.events.put(("token", "A streamed reply"))
    desktop.current_reply = ""
    desktop.active_reply_label = Control()
    desktop.root = type("Root", (), {"after": lambda *_args: None})()

    desktop._drain_events()

    assert desktop.current_reply == "A streamed reply"
    assert desktop.active_reply_label.config["text"] == "A streamed reply"


def test_message_bubble_uses_pack_padding_instead_of_invalid_label_option(monkeypatch):
    created_labels = []

    class FakeWidget:
        def __init__(self, _parent=None, **kwargs):
            self.options = kwargs
            self.pack_options = None

        def pack(self, **kwargs):
            self.pack_options = kwargs

    class FakeFrame(FakeWidget):
        pass

    class FakeLabel(FakeWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_labels.append(self)

    monkeypatch.setattr(gui_app.tk, "Frame", FakeFrame)
    monkeypatch.setattr(gui_app.tk, "Label", FakeLabel)
    monkeypatch.setattr(gui_app, "RoundedFrame", FakeFrame)
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.message_frame = FakeFrame()
    desktop.workspace = type("Workspace", (), {"winfo_width": lambda _self: 900})()
    desktop._persona_name = lambda: "Riko"

    desktop._add_message("you", "hello")

    body = created_labels[-1]
    assert "pady" not in body.options
    assert body.pack_options["pady"] == (0, 11)


def test_send_button_becomes_stop_and_cancels_text_generation():
    class Conversation:
        stopped = False

        def stop_response_generation(self):
            self.stopped = True

    conversation = Conversation()
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.mode_var = Value("text")
    desktop.busy = True
    desktop.response_cancel_requested = False
    desktop.voice_stopping = False
    desktop.current_turn_mode = "text"
    desktop.active_conversation = conversation
    desktop.send_button = Control()
    desktop.status_var = Value("")

    desktop._refresh_send_button()
    assert desktop.send_button.config["text"] == "■  Stop"
    assert desktop.send_button.config["state"] == "normal"

    desktop._action_button_pressed()

    assert conversation.stopped
    assert desktop.response_cancel_requested
    assert desktop.status_var.get() == "Stopping the response…"
    assert desktop.send_button.config["text"] == "Stopping…"
    assert desktop.send_button.config["state"] == "disabled"


def test_voice_reply_shows_stop_control_without_showing_text_composer():
    class VoiceSession:
        stopped = False

        def stop_response_generation(self):
            self.stopped = True

    session = VoiceSession()
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.mode_var = Value("voice")
    desktop.busy = True
    desktop.response_cancel_requested = False
    desktop.voice_stopping = False
    desktop.current_turn_mode = "voice"
    desktop.voice_session = session
    desktop.status_var = Value("")
    desktop.send_button = Control()

    desktop._refresh_send_button()

    assert any(call[0] == "pack" for call in desktop.send_button.calls)
    assert desktop.send_button.config["text"] == "■  Stop"

    desktop._action_button_pressed()

    assert session.stopped
    assert desktop.response_cancel_requested
    assert desktop.send_button.config["text"] == "Stopping…"


def test_preferences_can_be_saved_during_generation():
    class Prompts:
        selected = None

        def select_persona(self, persona):
            self.selected = persona

    class Settings:
        def __init__(self):
            self.voice = None
            self.speed = None

        def set_tts_voice(self, voice, _available):
            self.voice = voice

        def set_tts_speed(self, speed):
            self.speed = speed

    prompts = Prompts()
    settings = Settings()
    desktop = gui_app.RikoDesktop.__new__(gui_app.RikoDesktop)
    desktop.busy = True
    desktop.voice_session_active = True
    desktop.prompts = prompts
    desktop.settings = settings
    desktop.persona_choice = Value("tutor")
    desktop.voice_var = Value("af_heart")
    desktop.speed_var = Value(1.25)
    desktop.voice_values = ["af_heart"]
    desktop.settings_window = None
    desktop.events = queue.Queue()

    desktop.save_settings()

    assert prompts.selected == "tutor"
    assert settings.voice == "af_heart"
    assert settings.speed == 1.25
    assert desktop.events.get_nowait() == ("settings_saved", None)
