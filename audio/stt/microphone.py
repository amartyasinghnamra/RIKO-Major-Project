
"""Non-blocking microphone capture for RIKO's STT pipeline."""

from __future__ import annotations

import queue
import threading

import numpy as np
import sounddevice as sd


class MicrophoneCapture:
    """Capture microphone audio and deliver chunks through a queue."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        block_duration: float = 0.1,
        queue_size: int = 100,
        device=None,
    ):
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if channels <= 0:
            raise ValueError("channels must be positive")
        if block_duration <= 0:
            raise ValueError("block_duration must be positive")
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")

        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = max(1, round(sample_rate * block_duration))
        self.device = device
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(
            maxsize=queue_size
        )
        self._stream = None
        self._lock = threading.Lock()
        self._running = False
        self._dropped_chunks = 0
        self._callback_errors = []

    @property
    def running(self) -> bool:
        return self._running

    @property
    def dropped_chunks(self) -> int:
        return self._dropped_chunks

    @property
    def callback_errors(self) -> list[str]:
        with self._lock:
            return list(self._callback_errors)

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            with self._lock:
                self._callback_errors.append(str(status))

        chunk = np.array(indata, dtype=np.float32, copy=True)

        if chunk.ndim == 2 and chunk.shape[1] > 1:
            chunk = np.mean(chunk, axis=1, dtype=np.float32)
        else:
            chunk = chunk.reshape(-1)

        try:
            self.audio_queue.put_nowait(chunk)
        except queue.Full:
            with self._lock:
                self._dropped_chunks += 1

    def start(self):
        if self._running:
            return

        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.block_size,
            device=self.device,
            callback=self._audio_callback,
        )

        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

        self._running = True

    def read(self, timeout: float | None = 1.0) -> np.ndarray:
        return self.audio_queue.get(timeout=timeout)

    def stop(self):
        stream = self._stream
        self._stream = None
        self._running = False

        if stream is not None:
            try:
                if stream.active:
                    stream.stop()
            finally:
                stream.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
