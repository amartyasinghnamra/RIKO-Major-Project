
"""Persistent local settings for RIKO."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS = {
    "persona": "assistant",
    "tts": {
        "engine": "kokoro",
        "voice": "af_sarah",
        "speed": 1.0,
        "language": "en-us",
    },
}

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


class SettingsManager:
    """Read and safely update config/local/config.json."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self.path = self.project_root / "config" / "local" / "config.json"

    def load(self) -> dict[str, Any]:
        settings = json.loads(json.dumps(DEFAULT_SETTINGS))

        if not self.path.exists():
            return settings

        try:
            with self.path.open("r", encoding="utf-8") as file:
                stored = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Cannot read RIKO settings at {self.path}: {exc}"
            ) from exc

        if not isinstance(stored, dict):
            raise ValueError("RIKO settings must be a JSON object.")

        settings.update({
            key: value
            for key, value in stored.items()
            if key != "tts"
        })

        stored_tts = stored.get("tts", {})
        if stored_tts is not None:
            if not isinstance(stored_tts, dict):
                raise ValueError("'tts' settings must be a JSON object.")
            settings["tts"].update(stored_tts)

        return settings

    def save(self, settings: dict[str, Any]) -> None:
        if not isinstance(settings, dict):
            raise TypeError("settings must be a dictionary")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".config-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temp_path = Path(file.name)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())

            temp_path.replace(self.path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    @staticmethod
    def _validate_identifier(value: str, field: str) -> str:
        if (
            not isinstance(value, str)
            or not _IDENTIFIER.fullmatch(value)
        ):
            raise ValueError(f"Invalid {field} identifier: {value!r}")
        return value

    def get_persona(self) -> str:
        value = self.load().get("persona", "assistant")
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            return "assistant"
        return value

    def set_persona(self, persona_id: str) -> None:
        persona_id = self._validate_identifier(persona_id, "persona")
        settings = self.load()
        settings["persona"] = persona_id
        self.save(settings)

    def get_tts_settings(self) -> dict[str, Any]:
        return dict(self.load()["tts"])

    def get_tts_voice(self) -> str:
        voice = self.get_tts_settings().get("voice", "af_sarah")
        if not isinstance(voice, str) or not _IDENTIFIER.fullmatch(voice):
            return "af_sarah"
        return voice

    def set_tts_voice(
        self,
        voice_id: str,
        available_voices: list[str],
    ) -> None:
        voice_id = self._validate_identifier(voice_id, "voice")

        if voice_id not in available_voices:
            raise ValueError(f"Unsupported Kokoro voice: {voice_id}")

        settings = self.load()
        settings["tts"]["voice"] = voice_id
        self.save(settings)

    def set_tts_speed(self, speed: float) -> None:
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not 0.25 <= speed <= 4.0
        ):
            raise ValueError("TTS speed must be between 0.25 and 4.0.")

        settings = self.load()
        settings["tts"]["speed"] = float(speed)
        self.save(settings)
