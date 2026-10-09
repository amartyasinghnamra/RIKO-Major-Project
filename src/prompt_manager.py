import json
from pathlib import Path


DEFAULT_PERSONA = "assistant"


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

        self.local_config_path = config_dir / "local" / "config.json"

        self.public_personas_dir = config_dir / "personas"
        self.local_personas_dir = config_dir / "local" / "personas"

        self.profile_path = (
            config_dir / "local" / "user_profile.json"
        )

        self.example_profile_path = (
            config_dir / "examples" / "user_profile.example.json"
        )

        self.template_path = (
            self.project_root / "prompts" / "system_prompt.txt"
        )

    def load_json(self, file_path):
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def resolve_persona_name(self):
        """Persona name: local config wins, else the neutral default."""
        if self.local_config_path.exists():
            try:
                local_config = self.load_json(self.local_config_path)
            except (json.JSONDecodeError, OSError):
                local_config = {}

            name = local_config.get("persona")

            if isinstance(name, str) and name.strip():
                return name.strip()

        return DEFAULT_PERSONA

    def load_persona(self, persona_name):
        """Load a persona, preferring a private local copy.

        Falls back to the bundled assistant persona so a missing or
        broken file never crashes the app.
        """
        candidates = [
            self.local_personas_dir / f"{persona_name}.json",
            self.public_personas_dir / f"{persona_name}.json",
        ]

        if persona_name != DEFAULT_PERSONA:
            candidates.append(
                self.public_personas_dir / f"{DEFAULT_PERSONA}.json"
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

    def load_behavior(self, persona):
        behavior = {}

        if self.default_behavior_path.exists():
            behavior = self.load_json(self.default_behavior_path)

        persona_behavior = persona.get("behavior")

        if isinstance(persona_behavior, dict):
            behavior = deep_merge(behavior, persona_behavior)

        if self.local_behavior_path.exists():
            behavior = deep_merge(
                behavior, self.load_json(self.local_behavior_path)
            )

        return behavior

    def resolve_profile(self):
        if self.profile_path.exists():
            return self.load_json(self.profile_path)

        return self.load_json(self.example_profile_path)

    def get_persona(self):
        """Public helper for the UI layer (name + greeting)."""
        return self.load_persona(self.resolve_persona_name())

    def build_prompt(self):
        persona = self.get_persona()
        behavior = self.load_behavior(persona)
        profile = self.resolve_profile()

        template = self.template_path.read_text(encoding="utf-8")

        return template.format(
            persona_name=persona.get("name", "Riko"),
            persona_description=persona.get(
                "description", "A helpful local AI companion."
            ),
            user_profile=json.dumps(
                profile, indent=2, ensure_ascii=False
            ),
            behavior_instructions=json.dumps(
                behavior, indent=2, ensure_ascii=False
            ),
        )
