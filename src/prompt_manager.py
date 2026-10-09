
import json
from pathlib import Path


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

    def build_prompt(self):
        if self.local_behavior_path.exists():
            behavior_path = self.local_behavior_path
        else:
            behavior_path = self.default_behavior_path

        if self.profile_path.exists():
            profile_path = self.profile_path
        else:
            profile_path = self.example_profile_path

        behavior = self.load_json(behavior_path)
        profile = self.load_json(profile_path)

        template = self.template_path.read_text(
            encoding="utf-8"
        )

        behavior_instructions = json.dumps(
            behavior,
            indent=2,
            ensure_ascii=False
        )

        user_profile = json.dumps(
            profile,
            indent=2,
            ensure_ascii=False
        )

        return template.format(
            user_profile=user_profile,
            behavior_instructions=behavior_instructions
        )
