"""Voice input pipeline: microphone -> silence detection -> STT."""

from __future__ import annotations

import queue
from pathlib import Path
from time import monotonic

import numpy as np
import soundfile as sf

from audio.stt.microphone import MicrophoneCapture
from audio.stt.silence_detector import SilenceDetector
from audio.stt.faster_whisper_stt import FasterWhisperSTT


SAMPLE_RATE = 16000


class VoiceInput:
    """Capture one utterance and convert it to text."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language_mode: str = "auto",
        silence_duration: float = 1.2,
	energy_threshold: float = 0.001,
        max_record_seconds: float = 20.0,
        speech_timeout: float = 10.0,
        microphone_device=None,
    ):
        self.silence_duration = silence_duration
        self.energy_threshold = energy_threshold
        self.max_record_seconds = max_record_seconds
        self.speech_timeout = speech_timeout
        self.microphone_device = microphone_device

        # Whisper loads once and is reused for subsequent utterances.
        self.stt = FasterWhisperSTT(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            language_mode=language_mode,
        )

    def listen_once(self) -> str:
        """Listen for one utterance and return its transcript."""
        detector = SilenceDetector(
            sample_rate=SAMPLE_RATE,
            silence_duration=self.silence_duration,
            energy_threshold=self.energy_threshold,
        )

        chunks = []
        speech_started = False

        print("\n[RIKO] Listening... Speak when ready.")

        try:
            with MicrophoneCapture(
                sample_rate=SAMPLE_RATE,
                device=self.microphone_device,
            ) as microphone:
                # Start timers after the microphone has started.
                started = monotonic()
                speech_started_at = None

                while True:
                    elapsed = monotonic() - started

                    if not speech_started and elapsed >= self.speech_timeout:
                        print("[RIKO] I didn't hear speech. Try again.")
                        return ""

                    if (
                        speech_started
                        and speech_started_at is not None
                        and elapsed - speech_started_at >= self.max_record_seconds
                    ):
                        print("[RIKO] Maximum recording time reached.")
                        break

                    try:
                        chunk = microphone.read(timeout=0.5)
                    except queue.Empty:
                        continue

                    chunks.append(chunk)

                    finished = detector.process(chunk)

                    if detector.speech_detected and not speech_started:
                        speech_started = True
                        speech_started_at = elapsed
                        print("[RIKO] Speech detected...")

                    if finished:
                        print("[RIKO] Speech captured.")
                        break

        except KeyboardInterrupt:
            raise

        if not speech_started or not chunks:
            return ""

        audio = np.concatenate(chunks).astype(np.float32)

        # Skip empty or nearly silent recordings.
        if not np.all(np.isfinite(audio)):
            print("[RIKO] Invalid microphone audio. Try again.")
            return ""

        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms < 1e-5:
            print("[RIKO] The recording was silent. Try again.")
            return ""

        print("[RIKO] Transcribing...")
        result = self.stt.transcribe(audio)
        transcript = result.text.strip()

        if not transcript:
            print("[RIKO] I couldn't understand that. Please try again.")
            return ""

        print(f"[You said] {transcript}")
        return transcript