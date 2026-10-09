
"""Persistent audio output for RIKO."""

from pathlib import Path
from threading import Lock

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioPlayback:
    def __init__(self, device=None):
        self.device = device
        self._lock = Lock()
        self._stream = None
        self._sample_rate = None
        self._channels = None

    def _ensure_stream(self, sample_rate, channels):
        if (
            self._stream is not None
            and self._sample_rate == sample_rate
            and self._channels == channels
        ):
            return

        self._close_stream()

        self._stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            device=self.device,
            latency="low",
        )
        self._stream.start()
        self._sample_rate = sample_rate
        self._channels = channels

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
            finally:
                self._stream.close()
                self._stream = None
                self._sample_rate = None
                self._channels = None

    def play_samples(self, samples, sample_rate: int) -> None:
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")

        audio = np.asarray(samples, dtype=np.float32)

        if audio.size == 0:
            return

        if not np.isfinite(audio).all():
            raise ValueError("Audio contains NaN or infinity")

        if audio.ndim == 1:
            audio = audio.reshape(-1, 1)
        elif audio.ndim != 2:
            raise ValueError("Audio must be mono or multichannel")

        with self._lock:
            self._ensure_stream(sample_rate, audio.shape[1])
            self._stream.write(audio)

    def play_file(self, file_path) -> None:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")

        samples, sample_rate = sf.read(
            str(path),
            dtype="float32",
            always_2d=False,
        )
        self.play_samples(samples, sample_rate)

    def flush_tail(self, sample_rate=24000, milliseconds=150):
        """Give the final audio buffer time to drain naturally."""
        silence = np.zeros(
            int(sample_rate * milliseconds / 1000),
            dtype=np.float32,
        )
        self.play_samples(silence, sample_rate)

    def stop(self) -> None:
        with self._lock:
            self._close_stream()
