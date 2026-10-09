"""Streaming Kokoro TTS engine for RIKO.

Pipeline:
    text producer -> sentence queue -> Kokoro streaming synthesis
    -> audio queue -> playback consumer

Text Chat does not need to import this module.
"""

from __future__ import annotations

import asyncio
import queue
import re
import threading
from pathlib import Path
from typing import Iterable

from kokoro_onnx import Kokoro
from audio.playback import AudioPlayback


def remove_emojis(text: str) -> str:
    """Remove common emoji characters from voice-mode text."""
    return re.sub(
        "["
        "\U0001F000-\U0001FAFF"
        "\U00002700-\U000027BF"
        "\U00002600-\U000026FF"
        "\U0000FE0F"
        "\U0000200D"
        "]+",
        "",
        text,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = PROJECT_ROOT / "models" / "kokoro" / "kokoro-v1.0.int8.onnx"
DEFAULT_VOICES = PROJECT_ROOT / "models" / "kokoro" / "voices-v1.0.bin"

_END = object()


class KokoroTTS:
    """Streaming TTS with synthesis and playback running concurrently."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL,
        voices_path: str | Path = DEFAULT_VOICES,
        voice: str = "af_sarah",
        speed: float = 1.0,
        lang: str = "en-us",
        device=None,
        max_chunk_chars: int = 120,
    ):
        if speed <= 0:
            raise ValueError("speed must be greater than zero")
        if max_chunk_chars < 40:
            raise ValueError("max_chunk_chars must be at least 40")

        self.model_path = Path(model_path)
        self.voices_path = Path(voices_path)
        self.voice = voice
        self.speed = speed
        self.lang = lang
        self.max_chunk_chars = max_chunk_chars

        self._tts = None
        self._load_lock = threading.Lock()
        self._operation_lock = threading.Lock()
        self._playback = AudioPlayback()

    def load(self) -> None:
        """Load the model once."""
        with self._load_lock:
            if self._tts is not None:
                return

            if not self.model_path.is_file():
                raise FileNotFoundError(
                    f"Kokoro model not found: {self.model_path}"
                )

            if not self.voices_path.is_file():
                raise FileNotFoundError(
                    f"Kokoro voices file not found: {self.voices_path}"
                )

            self._tts = Kokoro(
                str(self.model_path),
                str(self.voices_path),
            )

    def synthesize(self, text: str):
        """Synthesize one complete piece of text without playing it."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        text = text.strip()
        if not text:
            raise ValueError("Cannot synthesize empty text")

        self.load()

        samples, sample_rate = self._tts.create(
            text,
            voice=self.voice,
            speed=self.speed,
            lang=self.lang,
        )
        return samples, sample_rate

    def speak_text(self, text: str) -> None:
        """Synthesize and play one complete piece of text."""
        if not text or not text.strip():
            return

        with self._operation_lock:
            samples, sample_rate = self.synthesize(text)
            self._playback.play_samples(samples, sample_rate)

    def speak_multiline(self, text: str) -> None:
        """Speak non-empty lines in order."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        for line in text.splitlines():
            if line.strip():
                self.speak_text(line.strip())

    def speak_file(self, file_path: str | Path, encoding="utf-8") -> None:
        """Speak non-empty lines from a UTF-8 text file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Text file not found: {path}")

        self.speak_multiline(path.read_text(encoding=encoding))

    def _split_ready_chunks(self, buffer: str, final=False):
        """Split available text into speakable phrases."""
        chunks = []

        while buffer.strip():
            # Prefer sentence boundaries.
            match = re.search(r"(?<=[.!?])\s+", buffer)

            if match:
                chunk = buffer[:match.start()].strip()
                buffer = buffer[match.end():]

                if chunk:
                    chunks.append(chunk)
                continue

            # Also allow shorter phrase boundaries for lower latency.
            if len(buffer) >= self.max_chunk_chars:
                limit = self.max_chunk_chars
                prefix = buffer[:limit]

                matches = list(
                    re.finditer(r"[,;:]\s+|\s+", prefix)
                )

                if matches:
                    # Prefer punctuation when it occurs reasonably early.
                    punctuation = [
                        m for m in matches
                        if m.group(0).strip() in {",", ";", ":"}
                        and m.start() >= limit // 2
                    ]
                    split_at = (
                        punctuation[-1].end()
                        if punctuation
                        else matches[-1].end()
                    )
                else:
                    split_at = limit

                chunk = buffer[:split_at].strip()
                buffer = buffer[split_at:].lstrip()

                if chunk:
                    chunks.append(chunk)
                continue

            break

        if final and buffer.strip():
            chunks.append(buffer.strip())
            buffer = ""

        return chunks, buffer

    def speak_stream(self, token_iterator: Iterable[str]) -> str:
        """Consume streaming text, synthesize audio chunks, and play them.

        Text production, Kokoro streaming synthesis, and playback overlap.
        Returns the complete text received from the iterator.
        """
        self.load()

        text_queue = queue.Queue()
        audio_queue = queue.Queue()
        errors = queue.Queue()
        full_text = []

        def produce_text():
            buffer = ""

            try:
                for token in token_iterator:
                    if not isinstance(token, str):
                        continue

                    token = remove_emojis(token)

                    if not token:
                        continue

                    full_text.append(token)
                    buffer += token

                    chunks, buffer = self._split_ready_chunks(buffer)
                    for chunk in chunks:
                        text_queue.put(chunk)

                chunks, buffer = self._split_ready_chunks(
                    buffer, final=True
                )
                for chunk in chunks:
                    text_queue.put(chunk)

            except Exception as exc:
                errors.put(exc)
            finally:
                text_queue.put(_END)

        async def synthesize_phrase(text):
            # Kokoro yields audio fragments while synthesizing this phrase.
            async for samples, sample_rate in self._tts.create_stream(
                text,
                voice=self.voice,
                speed=self.speed,
                lang=self.lang,
            ):
                audio_queue.put((samples, sample_rate))

        def synthesize_audio():
            try:
                while True:
                    item = text_queue.get()

                    if item is _END:
                        break

                    asyncio.run(synthesize_phrase(item))

            except Exception as exc:
                errors.put(exc)
            finally:
                audio_queue.put(_END)

        text_thread = threading.Thread(
            target=produce_text,
            name="riko-text-producer",
            daemon=True,
        )
        tts_thread = threading.Thread(
            target=synthesize_audio,
            name="riko-kokoro-stream",
            daemon=True,
        )

        last_sample_rate = 24000
        playback_error = None

        with self._operation_lock:
            text_thread.start()
            tts_thread.start()

            try:
                while True:
                    item = audio_queue.get()

                    if item is _END:
                        break

                    samples, sample_rate = item
                    last_sample_rate = sample_rate
                    self._playback.play_samples(samples, sample_rate)

                # Let the final audio drain naturally.
                self._playback.flush_tail(
                    sample_rate=last_sample_rate,
                    milliseconds=120,
                )

            except Exception as exc:
                playback_error = exc
                self._playback.stop()

            finally:
                text_thread.join()
                tts_thread.join()

        if playback_error is not None:
            raise playback_error

        if not errors.empty():
            raise errors.get()

        return "".join(full_text)

    def stop(self) -> None:
        """Stop current audio playback."""
        self._playback.stop()
