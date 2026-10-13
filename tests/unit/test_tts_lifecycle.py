"""Regression tests for RIKO's audio playback lifecycle."""

import threading

import pytest

from audio.playback import AudioPlayback
from audio.kokoro.tts import KokoroTTS


def test_stop_closes_the_active_output_stream():
    playback = AudioPlayback()

    class FakeStream:
        stopped = False
        closed = False

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    stream = FakeStream()
    playback._stream = stream
    playback._sample_rate = 24000
    playback._channels = 1

    playback.stop()

    assert stream.stopped
    assert stream.closed
    assert playback._stream is None
    assert playback._sample_rate is None
    assert playback._channels is None


def test_stop_is_safe_when_no_stream_exists():
    AudioPlayback().stop()


def test_playback_failure_does_not_leave_worker_threads_running():
    tts = KokoroTTS.__new__(KokoroTTS)
    tts._tts = object()
    tts._load_lock = threading.Lock()
    tts._operation_lock = threading.Lock()
    tts._playback = type(
        "FakePlayback",
        (),
        {
            "play_samples": lambda self, samples, rate: (
                (_ for _ in ()).throw(RuntimeError("playback failed"))
            ),
            "stop": lambda self: None,
            "flush_tail": lambda self, **kwargs: None,
        },
    )()
    tts.voice = "af_sarah"
    tts.speed = 1.0
    tts.lang = "en-us"
    tts.max_chunk_chars = 120

    async def fake_create_stream(*args, **kwargs):
        yield [0.1] * 32, 24000

    tts._tts = type(
        "FakeKokoro",
        (),
        {"create_stream": fake_create_stream},
    )()

    with pytest.raises(RuntimeError, match="playback failed"):
        tts.speak_stream(iter(["This is a sentence."]))

    active_workers = [
        thread.name
        for thread in threading.enumerate()
        if thread.name in {"riko-text-producer", "riko-kokoro-stream"}
    ]
    assert active_workers == []
