"""Streaming Kokoro TTS engine for RIKO.

Pipeline:
    text producer -> sentence queue -> Kokoro streaming synthesis
    -> audio queue -> playback consumer

Text Chat does not need to import this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import queue
import re
import tempfile
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


def markdown_to_speech(text: str) -> str:
    """Remove Markdown presentation syntax while keeping readable content."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    # Keep the human-readable link or image label, not its markup or URL.
    text = re.sub(r"!?\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}(?:```|~~~)[^\n]*", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s{0,3}>+\s?", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:[-+*]|\d+[.)])\s+", "", text)
    text = re.sub(r"(?m)^\s*(?:-{3,}|_{3,}|\*{3,})\s*$", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+.!>~-])", r"\1", text)

    # Formatting markers are silent. In particular, remove every asterisk
    # even when an Ollama stream splits a **bold** span between tokens.
    text = re.sub(r"[*_`~]", "", text)
    text = text.replace("|", " ")
    return re.sub(r"\s+", " ", text).strip()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = PROJECT_ROOT / "models" / "kokoro" / "kokoro-v1.0.int8.onnx"
DEFAULT_VOICES = PROJECT_ROOT / "models" / "kokoro" / "voices-v1.0.bin"
DEFAULT_CACHE = PROJECT_ROOT / "config" / "local" / "audio_cache"

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
        cache_enabled: bool = False,
        cache_dir: str | Path | None = None,
        max_cache_bytes: int = 128 * 1024 * 1024,
    ):
        if speed <= 0:
            raise ValueError("speed must be greater than zero")
        if max_chunk_chars < 40:
            raise ValueError("max_chunk_chars must be at least 40")
        if max_cache_bytes < 0:
            raise ValueError("max_cache_bytes cannot be negative")

        self.model_path = Path(model_path)
        self.voices_path = Path(voices_path)
        self.voice = voice
        self.speed = speed
        self.lang = lang
        self.max_chunk_chars = max_chunk_chars
        self.cache_enabled = bool(cache_enabled)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE
        self.max_cache_bytes = int(max_cache_bytes)

        self._tts = None
        self._load_lock = threading.Lock()
        self._operation_lock = threading.Lock()
        self._cancel_event = threading.Event()
        # Signals that speak_stream owns the audio operation and may be monitored.
        self._stream_active_event = threading.Event()
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

        cached = self._read_audio_cache(text)
        if cached is not None:
            return cached

        samples, sample_rate = self._tts.create(
            text,
            voice=self.voice,
            speed=self.speed,
            lang=self.lang,
        )
        self._write_audio_cache(text, samples, sample_rate)
        return samples, sample_rate

    def _audio_cache_path(self, text: str) -> Path | None:
        """Return a model/settings-sensitive cache name for one utterance."""
        try:
            model_stat = self.model_path.stat()
            voices_stat = self.voices_path.stat()
        except OSError:
            return None
        cache_identity = {
            "version": 1,
            "text": text,
            "voice": self.voice,
            "speed": float(self.speed),
            "language": self.lang,
            "model": [model_stat.st_size, model_stat.st_mtime_ns],
            "voices": [voices_stat.st_size, voices_stat.st_mtime_ns],
        }
        digest = hashlib.sha256(
            json.dumps(cache_identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"riko-{digest}.npz"

    def _read_audio_cache(self, text: str):
        if not getattr(self, "cache_enabled", False):
            return None
        cache_path = self._audio_cache_path(text)
        if cache_path is None or not cache_path.is_file():
            return None
        try:
            import numpy as np

            with np.load(cache_path, allow_pickle=False) as cached:
                samples = np.asarray(cached["samples"], dtype=np.float32)
                sample_rate = int(cached["sample_rate"][0])
            if samples.ndim != 1 or not samples.size or sample_rate <= 0:
                return None
            os.utime(cache_path, None)
            return samples, sample_rate
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            # A partial or stale cache entry must never prevent fresh speech.
            return None

    def _write_audio_cache(self, text: str, samples, sample_rate: int) -> None:
        if not getattr(self, "cache_enabled", False) or not getattr(self, "max_cache_bytes", 0):
            return
        cache_path = self._audio_cache_path(text)
        if cache_path is None or cache_path.exists():
            return
        temp_path = None
        try:
            import numpy as np

            audio = np.asarray(samples, dtype=np.float32)
            rate = int(sample_rate)
            if audio.ndim != 1 or not audio.size or rate <= 0:
                return

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                dir=self.cache_dir,
                prefix=".riko-audio-",
                suffix=".tmp",
                delete=False,
            ) as cache_file:
                temp_path = Path(cache_file.name)
                np.savez_compressed(
                    cache_file,
                    samples=audio,
                    sample_rate=np.asarray([rate], dtype=np.int32),
                )
                cache_file.flush()
                os.fsync(cache_file.fileno())

            # A hard link publishes a complete cache entry without replacing
            # a file that appeared concurrently or was created by the user.
            os.link(temp_path, cache_path)
            self._trim_audio_cache()
        except (OSError, ValueError, TypeError):
            # Caching is an optional optimization; TTS itself stays available.
            pass
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _trim_audio_cache(self) -> None:
        try:
            entries = [
                path for path in self.cache_dir.glob("riko-*.npz")
                if path.is_file()
            ]
            total = sum(path.stat().st_size for path in entries)
            for path in sorted(entries, key=lambda item: item.stat().st_mtime):
                if total <= self.max_cache_bytes:
                    break
                size = path.stat().st_size
                path.unlink()
                total -= size
        except OSError:
            pass

    @staticmethod
    def clear_cache(cache_dir: str | Path = DEFAULT_CACHE) -> int:
        """Remove only RIKO-generated audio-cache entries in the chosen folder."""
        directory = Path(cache_dir)
        if not directory.is_dir():
            return 0
        removed = 0
        for path in directory.glob("riko-*.npz"):
            if not path.is_file():
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    def speak_text(
        self,
        text: str,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Synthesize and play one complete piece of text."""
        if not text or not text.strip():
            return

        with self._operation_lock:
            if cancel_event is not None and cancel_event.is_set():
                return
            samples, sample_rate = self.synthesize(text)
            if cancel_event is not None and cancel_event.is_set():
                return
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

            def enqueue_speech(text: str) -> None:
                spoken = markdown_to_speech(text)
                if spoken:
                    text_queue.put(spoken)

            try:
                for token in token_iterator:
                    if self._cancel_event.is_set():
                        break
                    # A status event is spoken, but never included in
                    # the returned assistant response or conversation text.
                    if (
                        isinstance(token, tuple)
                        and len(token) == 2
                        and token[0] == "__RIKO_STATUS__"
                    ):
                        status = markdown_to_speech(remove_emojis(str(token[1])))
                        if status:
                            # Preserve ordering if an answer fragment is
                            # waiting in the text buffer.
                            if buffer.strip():
                                enqueue_speech(buffer.strip())
                                buffer = ""
                            enqueue_speech(status)
                        continue

                    if not isinstance(token, str):
                        continue

                    token = remove_emojis(token)

                    if not token:
                        continue

                    full_text.append(token)
                    buffer += token

                    chunks, buffer = self._split_ready_chunks(buffer)
                    for chunk in chunks:
                        enqueue_speech(chunk)

                chunks, buffer = self._split_ready_chunks(
                    buffer, final=True
                )
                for chunk in chunks:
                    enqueue_speech(chunk)

            except Exception as exc:
                errors.put(exc)
            finally:
                close = getattr(token_iterator, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception as exc:
                        errors.put(exc)
                text_queue.put(_END)

        async def synthesize_phrase(text):
            # Stop queuing fragments as soon as cancellation is observed.
            async for samples, sample_rate in self._tts.create_stream(
                text,
                voice=self.voice,
                speed=self.speed,
                lang=self.lang,
            ):
                if self._cancel_event.is_set():
                    break
                audio_queue.put((samples, sample_rate))

        def synthesize_audio():
            try:
                while not self._cancel_event.is_set():
                    try:
                        item = text_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if item is _END:
                        break

                    if self._cancel_event.is_set():
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

        # Tests and some lightweight callers may construct this object
        # with __new__, bypassing __init__. Initialize the event if needed.
        if not hasattr(self, "_cancel_event"):
            self._cancel_event = threading.Event()
        if not hasattr(self, "_stream_active_event"):
            self._stream_active_event = threading.Event()

        # Reset only after this operation owns the lock, so an active
        # operation's cancellation cannot be accidentally cleared.
        with self._operation_lock:
            self._cancel_event.clear()
            self._stream_active_event.set()
            text_thread.start()
            tts_thread.start()

            try:
                while not self._cancel_event.is_set():
                    try:
                        item = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if item is _END:
                        break

                    if self._cancel_event.is_set():
                        break

                    samples, sample_rate = item
                    last_sample_rate = sample_rate
                    self._playback.play_samples(samples, sample_rate)

                # Drain naturally only when playback was not cancelled.
                if not self._cancel_event.is_set():
                    self._playback.flush_tail(
                        sample_rate=last_sample_rate,
                        milliseconds=120,
                    )

            except Exception as exc:
                playback_error = exc
                self._cancel_event.set()
                self._playback.stop()

            finally:
                # Workers are daemon threads; bounded joins prevent a
                # stuck model/iterator from hanging the caller forever.
                text_thread.join(timeout=1.0)
                tts_thread.join(timeout=1.0)
                self._stream_active_event.clear()

        if playback_error is not None:
            raise playback_error

        if not errors.empty():
            raise errors.get()

        return "".join(full_text)

    def stop(self) -> None:
        """Cancel pending playback and stop current audio."""
        self._cancel_event.set()
        self._playback.stop()
