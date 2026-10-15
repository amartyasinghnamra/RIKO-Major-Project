"""Energy-based barge-in prototype for RIKO voice chat.

This is not acoustic echo cancellation. Headphones are recommended because
speaker audio can otherwise be mistaken for user speech.
"""
from __future__ import annotations

import queue
import threading
from time import monotonic

import numpy as np

from audio.stt.microphone import MicrophoneCapture
from audio.stt.silence_detector import SilenceDetector

SAMPLE_RATE = 16000


class BargeInMonitor:
    """Monitor microphone audio during TTS and transcribe an interruption."""

    def __init__(self, stt, tts, microphone_device=None,
                 energy_threshold=0.025, confirmation_seconds=0.30,
                 silence_duration=0.8, max_record_seconds=15.0,
                 on_interruption=None):
        if energy_threshold <= 0 or confirmation_seconds <= 0:
            raise ValueError("energy_threshold and confirmation_seconds must be positive")
        if silence_duration <= 0 or max_record_seconds <= 0:
            raise ValueError("silence_duration and max_record_seconds must be positive")
        self.stt = stt
        self.tts = tts
        self.microphone_device = microphone_device
        self.energy_threshold = float(energy_threshold)
        self.confirmation_seconds = float(confirmation_seconds)
        self.silence_duration = float(silence_duration)
        self.max_record_seconds = float(max_record_seconds)
        self.on_interruption = on_interruption
        self.interrupted = threading.Event()
        self.started = threading.Event()

    def listen(self, stop_event: threading.Event) -> str | None:
        """Wait for active TTS; interrupt on sustained energy and return its transcript."""
        while not stop_event.is_set():
            if self.tts._stream_active_event.wait(timeout=0.05):
                break
        else:
            return None

        if stop_event.is_set() or not self.tts._stream_active_event.is_set():
            return None

        chunks = []
        pre_roll = []
        pre_roll_limit = 5  # roughly 0.5 s for 100 ms microphone blocks
        above_seconds = 0.0
        recording_started = None
        detector = SilenceDetector(
            sample_rate=SAMPLE_RATE,
            silence_duration=self.silence_duration,
            energy_threshold=self.energy_threshold,
        )

        with MicrophoneCapture(sample_rate=SAMPLE_RATE,
                               device=self.microphone_device,
                               queue_size=100) as microphone:
            self.started.set()
            while not stop_event.is_set():
                if not self.interrupted.is_set() and not self.tts._stream_active_event.is_set():
                    return None
                try:
                    chunk = microphone.read(timeout=0.1)
                except queue.Empty:
                    continue

                now = monotonic()
                rms = float(np.sqrt(np.mean(np.square(chunk), dtype=np.float64)))
                pre_roll.append(chunk)
                if len(pre_roll) > pre_roll_limit:
                    pre_roll.pop(0)

                if not self.interrupted.is_set():
                    if rms >= self.energy_threshold:
                        above_seconds += len(chunk) / SAMPLE_RATE
                    else:
                        above_seconds = 0.0
                    if above_seconds < self.confirmation_seconds:
                        continue

                    # Stop output immediately; keep recording until end-of-utterance.
                    self.interrupted.set()
                    if self.on_interruption is not None:
                        try:
                            self.on_interruption()
                        except Exception:
                            # Always stop audio and finish capturing the user,
                            # even if an optional host callback has a problem.
                            pass
                    self.tts.stop()
                    chunks = list(pre_roll)
                    recording_started = now
                    for prior_chunk in chunks:
                        detector.process(prior_chunk)
                    continue

                chunks.append(chunk)
                if detector.process(chunk):
                    break
                if recording_started is not None and now - recording_started >= self.max_record_seconds:
                    break

        if stop_event.is_set() or not self.interrupted.is_set() or not chunks:
            return None
        audio = np.concatenate(chunks).astype(np.float32, copy=False)
        if not np.all(np.isfinite(audio)):
            return None
        result = self.stt.transcribe(audio)
        transcript = getattr(result, "text", "").strip()
        return transcript or None
