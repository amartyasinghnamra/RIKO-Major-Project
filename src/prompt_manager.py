
import json
import re
from pathlib import Path

from settings_manager import SettingsManager
from user_profile import normalize_profile
from behavior_preferences import (
    extract_behavior_preferences,
    format_behavior_instructions,
    validate_behavior_preferences,
)


DEFAULT_PERSONA = "assistant"
DEFAULT_PROFILE = "user"
_PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def deep_merge(base, override):
    """Recursively merge override into base and return a new dict."""
    merged = dict(base)

    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


class PromptManager:
    def __init__(self, project_root):
        self.project_root = Path(project_root)

        config_dir = self.project_root / "config"

        self.default_behavior_path = (
            config_dir / "defaults" / "behavior.default.json"
        )
        self.local_behavior_path = (
            config_dir / "local" / "behavior.local.json"
        )
        self.local_config_path = (
            config_dir / "local" / "config.json"
        )
        self.settings = SettingsManager(self.project_root)

        self.public_personas_dir = config_dir / "personas"
        self.local_personas_dir = config_dir / "local" / "personas"

        self.profile_path = (
            config_dir / "local" / "user_profile.json"
        )
        self.example_profile_path = (
            config_dir / "examples" / "user_profile.example.json"
        )
        self.public_profiles_dir = config_dir / "examples" / "profiles"
        self.local_profiles_dir = config_dir / "local" / "profiles"

        prompts_dir = self.project_root / "prompts"
        self.template_path = prompts_dir / "system_prompt.txt"
        self.text_style_path = prompts_dir / "text_style.txt"
        self.voice_style_path = prompts_dir / "voice_style.txt"

    def load_json(self, file_path):
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def resolve_persona_name(self):
        """Resolve the selected persona from shared local settings."""
        return self.settings.get_persona()

    def list_personas(self):
        """List valid local and bundled persona definitions."""
        personas = {}

        for directory in (
            self.public_personas_dir,
            self.local_personas_dir,
        ):
            if not directory.is_dir():
                continue

            for path in sorted(directory.glob("*.json")):
                try:
                    persona = self.load_json(path)
                except (json.JSONDecodeError, OSError):
                    continue

                if not isinstance(persona, dict):
                    continue

                name = persona.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue

                personas[path.stem] = {
                    "id": path.stem,
                    "name": name.strip(),
                    "description": str(
                        persona.get("description", "")
                    ),
                }

        return [
            personas[key] for key in sorted(personas)
        ]

    def select_persona(self, persona_id):
        """Validate and persist a persona selection."""
        available_ids = {
            persona["id"] for persona in self.list_personas()
        }

        if not isinstance(persona_id, str) or persona_id not in available_ids:
            raise ValueError(
                f"Unknown persona {persona_id!r}. "
                f"Available personas: {', '.join(sorted(available_ids))}"
            )

        self.settings.set_persona(persona_id)

    def load_persona(self, persona_name):
        """Load a local persona first, then a bundled persona."""
        candidates = [
            self.local_personas_dir / f"{persona_name}.json",
            self.public_personas_dir / f"{persona_name}.json",
        ]

        if persona_name != DEFAULT_PERSONA:
            candidates.append(
                self.public_personas_dir
                / f"{DEFAULT_PERSONA}.json"
            )

        for path in candidates:
            if not path.exists():
                continue

            try:
                persona = self.load_json(path)
            except (json.JSONDecodeError, OSError):
                continue

            if isinstance(persona, dict):
                return persona

        return {
            "name": "Riko",
            "description": "A helpful local AI companion.",
            "greeting": "Hello! I'm here.",
            "behavior": {},
        }

    def load_behavior(self, persona, *, include_local=True):
        """Merge default, persona-specific, and local behavior."""
        behavior = {}

        if self.default_behavior_path.exists():
            behavior = self.load_json(
                self.default_behavior_path
            )

        persona_behavior = persona.get("behavior")

        if isinstance(persona_behavior, dict):
            behavior = deep_merge(
                behavior, persona_behavior
            )

        if include_local and self.local_behavior_path.exists():
            local_behavior = self.load_json(self.local_behavior_path)
            if not isinstance(local_behavior, dict):
                raise ValueError("Local behavior preferences must be a JSON object.")
            behavior = deep_merge(behavior, local_behavior)

        return behavior

    def get_behavior_preferences(self, *, include_local=True):
        """Return effective slider/dropdown values for the selected persona."""
        persona = self.get_persona()
        behavior = self.load_behavior(persona, include_local=include_local)
        return extract_behavior_preferences(behavior)

    def save_behavior_preferences(self, values):
        """Save validated user overrides without replacing other local behavior."""
        patch = validate_behavior_preferences(values)
        local_behavior = {}
        if self.local_behavior_path.exists():
            local_behavior = self.load_json(self.local_behavior_path)
            if not isinstance(local_behavior, dict):
                raise ValueError("Local behavior preferences must be a JSON object.")
        updated = deep_merge(local_behavior, patch)
        self._write_local_behavior(updated)

    def reset_behavior_preferences(self):
        """Remove only the UI-owned overrides, preserving custom local fields."""
        if not self.local_behavior_path.exists():
            return
        local_behavior = self.load_json(self.local_behavior_path)
        if not isinstance(local_behavior, dict):
            raise ValueError("Local behavior preferences must be a JSON object.")
        for section, keys in (
            ("personality", ("cuteness", "playfulness", "teasing", "warmth", "energy", "talkativeness", "spontaneity")),
            ("conversation", ("spontaneity", "initiative", "emotional_awareness", "reassurance", "response_style")),
        ):
            values = local_behavior.get(section)
            if not isinstance(values, dict):
                continue
            for key in keys:
                values.pop(key, None)
            if not values:
                local_behavior.pop(section, None)
        self._write_local_behavior(local_behavior)

    def _write_local_behavior(self, behavior):
        import os
        import tempfile

        self.local_behavior_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(behavior, indent=2, ensure_ascii=False) + "\n"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.local_behavior_path.parent,
                prefix=".behavior-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temp_path = Path(file.name)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            temp_path.replace(self.local_behavior_path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    def resolve_profile(self):
        """Load the selected local profile or a bundled profile preset."""
        return self.load_profile(self.settings.get_profile())

    def list_profiles(self):
        """List the personal profile and valid bundled/local profile presets."""
        profiles = {
            DEFAULT_PROFILE: {
                "id": DEFAULT_PROFILE,
                "name": "Personal profile",
                "description": "Your private profile saved on this computer.",
                "source": "local",
            }
        }

        # Bundled profile examples are read-only. A same-named local profile
        # takes precedence so users can keep private copies or custom profiles.
        for directory in (self.public_profiles_dir, self.local_profiles_dir):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                profile_id = path.stem
                if (
                    profile_id == DEFAULT_PROFILE
                    or not _PROFILE_ID.fullmatch(profile_id)
                ):
                    continue
                try:
                    raw_profile = self.load_json(path)
                    normalize_profile(raw_profile)
                except (json.JSONDecodeError, OSError, ValueError):
                    continue

                metadata = raw_profile.get("_meta", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                name = metadata.get("name")
                description = metadata.get("description", "")
                profiles[profile_id] = {
                    "id": profile_id,
                    "name": (
                        name.strip()
                        if isinstance(name, str) and name.strip()
                        else profile_id.replace("_", " ").title()
                    ),
                    "description": (
                        description.strip()
                        if isinstance(description, str)
                        else ""
                    ),
                    "source": "local" if directory == self.local_profiles_dir else "bundled",
                }

        return [profiles[key] for key in sorted(profiles)]

    def select_profile(self, profile_id):
        """Persist a profile selection after checking it is available."""
        available_ids = {profile["id"] for profile in self.list_profiles()}
        if not isinstance(profile_id, str) or profile_id not in available_ids:
            raise ValueError(
                f"Unknown profile {profile_id!r}. Available profiles: "
                f"{', '.join(sorted(available_ids))}"
            )
        self.settings.set_profile(profile_id)

    def profile_storage_path(self, profile_id):
        """Return a writable path for a personal or custom local profile."""
        if profile_id == DEFAULT_PROFILE:
            return self.profile_path
        if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
            raise ValueError(f"Invalid profile id: {profile_id!r}")
        local_path = self.local_profiles_dir / f"{profile_id}.json"
        if local_path.exists():
            return local_path
        if (self.public_profiles_dir / f"{profile_id}.json").exists():
            raise ValueError(
                f"The bundled {profile_id!r} profile is read-only. "
                "Copy it to a new profile id before editing."
            )
        return local_path

    def load_profile(self, profile_id=DEFAULT_PROFILE):
        """Resolve a profile id, preferring private local files to presets."""
        if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
            profile_id = DEFAULT_PROFILE

        if profile_id == DEFAULT_PROFILE:
            path = (
                self.profile_path
                if self.profile_path.exists()
                else self.example_profile_path
            )
        else:
            candidates = (
                self.local_profiles_dir / f"{profile_id}.json",
                self.public_profiles_dir / f"{profile_id}.json",
            )
            path = next((candidate for candidate in candidates if candidate.is_file()), None)
            if path is None:
                return self.load_profile(DEFAULT_PROFILE)

        return normalize_profile(self.load_json(path))

    def get_persona(self):
        """Return the resolved persona."""
        return self.load_persona(
            self.resolve_persona_name()
        )

    def build_prompt(self, mode="text"):
        """Build the common prompt and append the selected mode style."""
        if mode not in ("text", "voice"):
            raise ValueError(
                "mode must be either 'text' or 'voice'"
            )

        persona = self.get_persona()
        behavior = self.load_behavior(persona)
        profile = self.resolve_profile()

        template = self.template_path.read_text(
            encoding="utf-8"
        )

        common_prompt = template.format(
            persona_name=persona.get("name", "Riko"),
            persona_description=persona.get(
                "description",
                "A helpful local AI companion.",
            ),
            user_profile=json.dumps(
                profile,
                indent=2,
                ensure_ascii=False,
            ),
            behavior_instructions=format_behavior_instructions(behavior),
        )

        style_path = (
            self.voice_style_path
            if mode == "voice"
            else self.text_style_path
        )

        if style_path.exists():
            style_prompt = style_path.read_text(
                encoding="utf-8"
            ).strip()

            if style_prompt:
                return (
                    f"{common_prompt.rstrip()}\n\n"
                    "--- INTERFACE-SPECIFIC INSTRUCTIONS ---\n"
                    f"{style_prompt}\n"
                )

        return common_prompt
