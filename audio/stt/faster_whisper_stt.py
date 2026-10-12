"""Faster-Whisper transcription engine for RIKO.

Accepts mono float32 audio sampled at 16 kHz. The Whisper model is loaded
lazily once and reused for subsequent utterances.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class TranscriptionResult:
    """Normalized transcription result."""

    text: str
    language: str | None = None
    language_probability: float | None = None
    duration: float | None = None


class FasterWhisperSTT:
    """Reusable, CPU-friendly multilingual Faster-Whisper wrapper."""

    LANGUAGE_MODES = {"auto", "english", "hindi", "hinglish"}
    DEFAULT_INITIAL_PROMPT = None

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
        beam_size: int = 5,
        language_mode: str = "auto",
        vad_filter: bool = True,
        vad_threshold: float = 0.35,
        min_silence_duration_ms: int = 500,
        speech_pad_ms: int = 700,
        initial_prompt: str | None = DEFAULT_INITIAL_PROMPT,
        condition_on_previous_text: bool = False,
    ) -> None:
        if not model_size.strip():
            raise ValueError("model_size cannot be empty")
        if beam_size < 1:
            raise ValueError("beam_size must be positive")
        if language_mode not in self.LANGUAGE_MODES:
            raise ValueError(
                f"Unsupported language_mode: {language_mode}. "
                f"Choose one of {sorted(self.LANGUAGE_MODES)}."
            )
        if not 0.0 < vad_threshold <= 1.0:
            raise ValueError("vad_threshold must be in the range (0, 1]")
        if min_silence_duration_ms < 0 or speech_pad_ms < 0:
            raise ValueError("VAD durations cannot be negative")

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.language_mode = language_mode
        self.vad_filter = vad_filter
        self.vad_threshold = vad_threshold
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms
        self.initial_prompt = initial_prompt
        self.condition_on_previous_text = condition_on_previous_text
        self._model: Any | None = None

    def load(self) -> None:
        """Load the model once; subsequent calls reuse the same instance."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def _selected_language(self) -> str | None:
        # Explicit language wins. Hinglish has no dedicated Whisper language ID;
        # multilingual auto-detection is the safest default for code-switching.
        if self.language is not None:
            return self.language
        if self.language_mode == "hindi":
            return "hi"
        if self.language_mode == "english":
            return "en"
        return None

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        """Transcribe one complete 16 kHz mono float32 utterance."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return TranscriptionResult(text="")
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite samples")
        if float(np.max(np.abs(samples))) < 1e-5:
            return TranscriptionResult(text="")

        self.load()
        vad_parameters = {
            "threshold": self.vad_threshold,
            "min_silence_duration_ms": self.min_silence_duration_ms,
            "speech_pad_ms": self.speech_pad_ms,
        }
        options: dict[str, Any] = {
            "language": self._selected_language(),
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
        }
        if self.vad_filter:
            options["vad_parameters"] = vad_parameters
        if self.initial_prompt:
            options["initial_prompt"] = self.initial_prompt

        # Faster-Whisper returns a lazy segment iterator; consume it here so
        # transcription completes before the result is returned.
        segments, info = self._model.transcribe(samples, **options)
        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()
        return TranscriptionResult(
            text=text,
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            duration=getattr(info, "duration", None),
        )
