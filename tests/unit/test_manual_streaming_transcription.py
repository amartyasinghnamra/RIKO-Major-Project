from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np

from audio.stt import streaming_voice_input as streaming_module
from audio.stt.streaming_voice_input import StreamingVoiceInput


def test_manual_stop_emits_live_drafts_and_finalizes_full_transcript(monkeypatch):
    clock = [0.0]
    stop_event = threading.Event()
    partials = []

    class FakeMicrophone:
        def __init__(self, **_kwargs):
            self.reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, timeout):
            assert timeout == 0.5
            self.reads += 1
            clock[0] += 0.1
            if self.reads >= 35:
                stop_event.set()
            return np.full(1600, 0.05, dtype=np.float32)

    class FakeSTT:
        def transcribe(self, audio):
            if len(audio) < 1600 * 30:
                return SimpleNamespace(text="live draft")
            return SimpleNamespace(text="final transcript", language="en")

    monkeypatch.setattr(streaming_module, "MicrophoneCapture", FakeMicrophone)
    monkeypatch.setattr(streaming_module, "monotonic", lambda: clock[0])
    voice = StreamingVoiceInput.__new__(StreamingVoiceInput)
    voice.silence_duration = 0.8
    voice.energy_threshold = 0.001
    voice.speech_timeout = 10.0
    voice.max_record_seconds = 120.0
    voice.update_interval = 0.2
    voice.window_seconds = 6.0
    voice.microphone_device = None
    voice.stt = FakeSTT()

    transcript = voice.listen_once(
        stop_event=stop_event,
        on_partial=partials.append,
        finalize_on_stop=True,
        manual_stop=True,
    )

    assert partials
    assert "live draft" in partials
    assert transcript == "final transcript"
