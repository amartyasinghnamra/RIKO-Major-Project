"""Discover voices supported by the loaded Kokoro model."""

from pathlib import Path

from kokoro_onnx import Kokoro

from audio.kokoro.tts import DEFAULT_MODEL, DEFAULT_VOICES


class KokoroVoiceRegistry:
    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL,
        voices_path: str | Path = DEFAULT_VOICES,
    ):
        self.model_path = Path(model_path)
        self.voices_path = Path(voices_path)

    def list_voices(self) -> list[str]:
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Kokoro model not found: {self.model_path}"
            )
        if not self.voices_path.is_file():
            raise FileNotFoundError(
                f"Kokoro voices file not found: {self.voices_path}"
            )

        engine = Kokoro(str(self.model_path), str(self.voices_path))
        return engine.get_voices()
