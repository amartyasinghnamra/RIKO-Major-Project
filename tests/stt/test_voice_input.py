
"""Standalone microphone -> silence detection -> Faster-Whisper test."""

from pathlib import Path
from time import monotonic

import numpy as np
import soundfile as sf

from audio.stt.microphone import MicrophoneCapture
from audio.stt.silence_detector import SilenceDetector
from audio.stt.faster_whisper_stt import FasterWhisperSTT


SAMPLE_RATE = 16000
OUTPUT = Path("tests/stt/live_input.wav")
MAX_RECORD_SECONDS = 15
WAIT_FOR_SPEECH_SECONDS = 10


def main():
    detector = SilenceDetector(
        sample_rate=SAMPLE_RATE,
        silence_duration=1.2,
        energy_threshold=0.012,
    )

    chunks = []
    speech_started = False
    started = monotonic()

    print("Speak a short sentence after recording starts.")
    print("Recording stops after 1.2 seconds of silence.")
    print("Press Ctrl+C to cancel.\n")

    try:
        with MicrophoneCapture(sample_rate=SAMPLE_RATE) as microphone:
            while True:
                elapsed = monotonic() - started

                if not speech_started and elapsed >= WAIT_FOR_SPEECH_SECONDS:
                    print("No speech detected. Please check your microphone.")
                    return

                if elapsed >= MAX_RECORD_SECONDS:
                    print("Maximum recording time reached.")
                    break

                try:
                    chunk = microphone.read(timeout=0.5)
                except __import__("queue").Empty:
                    continue

                chunks.append(chunk)

                if detector.process(chunk):
                    print("Speech finished.")
                    break

                if detector.speech_detected and not speech_started:
                    speech_started = True
                    print("Speech detected...")

    except KeyboardInterrupt:
        print("\nRecording cancelled.")
        return

    if not speech_started:
        print("No speech detected.")
        return

    audio = np.concatenate(chunks).astype(np.float32)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT, audio, SAMPLE_RATE)

    print(f"Saved recording: {OUTPUT}")
    print(f"Duration: {len(audio) / SAMPLE_RATE:.2f} seconds")

    stt = FasterWhisperSTT(
        model_size="small",
        device="cpu",
        compute_type="int8",
        language_mode="auto",
    )

    print("\nTranscribing...")
    result = stt.transcribe(audio)

    print("Transcript:", result.text or "[No speech recognized]")
    print("Detected language:", result.language)
    print("Language probability:", result.language_probability)


if __name__ == "__main__":
    main()
