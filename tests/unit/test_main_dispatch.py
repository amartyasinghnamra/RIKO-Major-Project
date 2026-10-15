"""The CLI entry point exposes the same mode calls to desktop hosts."""

from __future__ import annotations

import builtins
from unittest.mock import Mock

import main as riko_main


def test_main_menu_dispatches_text_to_shared_text_runner(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt: "1")
    run_text = Mock()
    monkeypatch.setattr(riko_main, "run_text_chat", run_text)

    riko_main.main()

    run_text.assert_called_once_with()


def test_main_menu_dispatches_voice_to_shared_voice_runner(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt: "2")
    run_voice = Mock()
    monkeypatch.setattr(riko_main, "run_voice_chat", run_voice)

    riko_main.main()

    run_voice.assert_called_once_with()


def test_gui_text_call_uses_main_text_function_for_one_turn():
    class FakeTextSession:
        def stream_response(self, message):
            yield f"reply:{message}"

        def run_cli(self):
            raise AssertionError("GUI text routing must not enter the CLI input loop")

    assert list(
        riko_main.run_text_chat(session=FakeTextSession(), message="hello")
    ) == ["reply:hello"]


def test_gui_voice_call_uses_main_voice_function_with_host_events():
    class FakeVoiceSession:
        def __init__(self):
            self.callback = None

        def run(self, callback):
            self.callback = callback

        def run_cli(self):
            raise AssertionError("GUI voice routing must not enter the CLI renderer")

    session = FakeVoiceSession()
    on_event = Mock()

    riko_main.run_voice_chat(session=session, on_event=on_event)

    assert session.callback is on_event


def test_cli_mode_runners_use_the_same_session_cli_methods():
    class FakeTextSession:
        def __init__(self):
            self.called = False

        def run_cli(self):
            self.called = True
            return "text-cli"

    class FakeVoiceSession:
        def __init__(self):
            self.called = False

        def run_cli(self):
            self.called = True
            return "voice-cli"

    text_session = FakeTextSession()
    voice_session = FakeVoiceSession()

    assert riko_main.run_text_chat(session=text_session) == "text-cli"
    assert riko_main.run_voice_chat(session=voice_session) == "voice-cli"
    assert text_session.called and voice_session.called
