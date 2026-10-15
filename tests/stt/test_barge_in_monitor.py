"""Voice interruption tests for the barge-in capture path."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np

from audio.stt import barge_in_monitor as barge_module
from audio.stt.barge_in_monitor import BargeInMonitor


def test_sustained_speech_stops_generation_and_captures_the_interruption(monkeypatch):
    callback_calls = []

    class FakeMicrophone:
        def __init__(self, **_kwargs):
            self.reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self, timeout=None):
            self.reads += 1
            if self.reads <= 3:
                return np.full(1600, 0.1, dtype=np.float32)
            return np.zeros(1600, dtype=np.float32)

    class FakeTTS:
        def __init__(self):
            self._stream_active_event = threading.Event()
            self._stream_active_event.set()
            self.stops = 0

        def stop(self):
            self.stops += 1
            self._stream_active_event.clear()

    class FakeSTT:
        def transcribe(self, audio):
            assert audio.size >= 1600
            return SimpleNamespace(text="stop")

    monkeypatch.setattr(barge_module, "MicrophoneCapture", FakeMicrophone)
    tts = FakeTTS()
    monitor = BargeInMonitor(
        stt=FakeSTT(),
        tts=tts,
        energy_threshold=0.025,
        confirmation_seconds=0.30,
        silence_duration=0.10,
        max_record_seconds=1.0,
        on_interruption=lambda: callback_calls.append("cancel"),
    )

    transcript = monitor.listen(threading.Event())

    assert transcript == "stop"
    assert callback_calls == ["cancel"]
    assert tts.stops == 1
    assert monitor.interrupted.is_set()
