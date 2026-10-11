
"""Energy-based silence detection for buffered microphone audio."""

from dataclasses import dataclass

import numpy as np


@dataclass
class SilenceDetector:
    """Detect significant silence using short-frame audio RMS energy.

    Audio must be mono float audio normalized approximately to [-1, 1].
    This is an energy-based detector, not a full voice activity detector.
    """

    sample_rate: int = 16000
    silence_duration: float = 1.2
    frame_duration: float = 0.02
    energy_threshold: float = 0.012

    def __post_init__(self):
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.silence_duration <= 0:
            raise ValueError("silence_duration must be positive")
        if self.frame_duration <= 0:
            raise ValueError("frame_duration must be positive")
        if self.energy_threshold < 0:
            raise ValueError("energy_threshold cannot be negative")

        self.reset()

    def reset(self):
        """Reset silence tracking for a new utterance."""
        self._silent_samples = 0
        self._speech_detected = False

    @property
    def speech_detected(self) -> bool:
        return self._speech_detected

    @property
    def silence_seconds(self) -> float:
        return self._silent_samples / self.sample_rate

    def process(self, audio: np.ndarray) -> bool:
        """Process an audio chunk; return True at the silence boundary.

        The caller should finalize the current utterance when this returns
        True, then call reset() before tracking the next utterance.
        """
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)

        if samples.size == 0:
            return False

        frame_size = max(1, round(self.sample_rate * self.frame_duration))

        for start in range(0, samples.size, frame_size):
            frame = samples[start:start + frame_size]
            rms = float(np.sqrt(np.mean(np.square(frame), dtype=np.float64)))

            if rms >= self.energy_threshold:
                self._speech_detected = True
                self._silent_samples = 0
            elif self._speech_detected:
                self._silent_samples += frame.size

                if self._silent_samples >= round(
                    self.sample_rate * self.silence_duration
                ):
                    return True

        return False
