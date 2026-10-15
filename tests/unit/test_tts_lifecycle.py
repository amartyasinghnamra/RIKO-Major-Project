"""Regression tests for RIKO's audio playback lifecycle."""

import threading

import pytest

from audio.playback import AudioPlayback
from audio.kokoro.tts import KokoroTTS, markdown_to_speech


def test_markdown_to_speech_removes_formatting_without_reading_asterisks():
    spoken = markdown_to_speech(
        "## Summary\nThis is **bold** and *italic*.\n- First item\n"
        "See [the guide](https://example.com)."
    )

    assert spoken == "Summary This is bold and italic. First item See the guide."
    assert "*" not in spoken


def test_streamed_markdown_is_cleaned_before_kokoro_synthesis():
    tts = KokoroTTS.__new__(KokoroTTS)
    tts._load_lock = threading.Lock()
    tts._operation_lock = threading.Lock()
    tts._cancel_event = threading.Event()
    tts._stream_active_event = threading.Event()
    tts.voice = "af_sarah"
    tts.speed = 1.0
    tts.lang = "en-us"
    tts.max_chunk_chars = 120
    tts.load = lambda: None
    synthesized = []

    async def fake_create_stream(_self, text, **_kwargs):
        synthesized.append(text)
        yield [0.1] * 32, 24000

    tts._tts = type("FakeKokoro", (), {"create_stream": fake_create_stream})()
    tts._playback = type(
        "FakePlayback",
        (),
        {
            "play_samples": lambda *_args: None,
            "flush_tail": lambda *_args, **_kwargs: None,
            "stop": lambda *_args: None,
        },
    )()

    original = "This is **bold** and *italic*."
    returned = tts.speak_stream(iter(["This is **bo", "ld** and *italic*."]))

    assert returned == original
    assert synthesized == ["This is bold and italic."]
    assert all("*" not in phrase for phrase in synthesized)


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

def test_stop_does_not_wait_for_the_playback_lock():
    playback = AudioPlayback()
    playback._lock.acquire()

    finished = threading.Event()

    def request_stop():
        try:
            playback.stop()
        finally:
            finished.set()

    worker = threading.Thread(target=request_stop, daemon=True)
    worker.start()

    try:
        assert finished.wait(timeout=0.5), (
            "stop() blocked waiting for the playback state lock"
        )
    finally:
        playback._lock.release()

    worker.join(timeout=1)
    assert not worker.is_alive()

def test_stop_during_active_write_aborts_and_closes_stream():
    playback = AudioPlayback()
    write_started = threading.Event()
    allow_write_to_finish = threading.Event()
    aborted = threading.Event()
    closed = threading.Event()

    class FakeStream:
        def write(self, audio):
            write_started.set()
            allow_write_to_finish.wait(timeout=2)

        def abort(self):
            aborted.set()
            allow_write_to_finish.set()

        def stop(self):
            pass

        def close(self):
            closed.set()

    stream = FakeStream()
    playback._stream = stream
    playback._sample_rate = 24000
    playback._channels = 1

    writer = threading.Thread(target=lambda: playback.play_samples([0.1] * 32, 24000), daemon=True)
    writer.start()
    assert write_started.wait(timeout=1), 'Audio write did not start'

    stopper = threading.Thread(target=playback.stop, daemon=True)
    stopper.start()
    assert aborted.wait(timeout=1), 'stop() did not abort the active stream'

    writer.join(timeout=2)
    stopper.join(timeout=2)
    assert not writer.is_alive(), 'Writer thread remained stuck'
    assert not stopper.is_alive(), 'Stop thread remained stuck'
    assert closed.is_set(), 'Stream was not closed'



def test_cancelled_stream_does_not_play_queued_audio():
    tts = KokoroTTS.__new__(KokoroTTS)
    tts._tts = object()
    tts._load_lock = threading.Lock()
    tts._operation_lock = threading.Lock()
    tts._cancel_event = threading.Event()
    tts._cancel_event.set()
    tts.voice = "af_sky"
    tts.speed = 1.0
    tts.lang = "en-us"
    tts.max_chunk_chars = 200

    class FakePlayback:
        def __init__(self):
            self.played = []
            self.stopped = False
        def play_samples(self, samples, sample_rate):
            self.played.append((samples, sample_rate))
        def flush_tail(self, **kwargs):
            pass
        def stop(self):
            self.stopped = True

    tts._playback = FakePlayback()
    tts.load = lambda: None

    def cancelled_text():
        tts._cancel_event.set()
        yield "This should not be played."

    try:
        tts.speak_stream(cancelled_text())
    except Exception:
        pass

    assert tts._playback.played == []


def test_speak_text_skips_synthesis_if_cancellation_was_requested():
    tts = KokoroTTS.__new__(KokoroTTS)
    tts._operation_lock = threading.Lock()
    tts._playback = type("Playback", (), {"play_samples": lambda *_args: None})()
    tts.synthesize = lambda _text: (_ for _ in ()).throw(
        AssertionError("cancelled speech should not be synthesized")
    )
    cancel_event = threading.Event()
    cancel_event.set()

    tts.speak_text("Cancelled before playback", cancel_event=cancel_event)
